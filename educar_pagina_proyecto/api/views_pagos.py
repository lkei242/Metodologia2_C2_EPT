"""API de cuotas, deuda, facturas, pagos y comprobantes.

Cubre RF-M03 a RF-M07. Todas las vistas validan rol y pertenencia del dato en el
servidor: un tutor solo ve a sus hijos, un alumno solo a sí mismo.
"""
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.permisos_dominio import PADRE, alumnos_visibles, exigir_alumno_visible, exigir_rol
from core.facturacion import generar_pdf_factura
from core.models import ComprobantePago, Cuota, Factura, ItemFactura, SolicitudPago

EXTENSIONES_COMPROBANTE = {
    '.pdf': b'%PDF',
    '.png': b'\x89PNG',
    '.jpg': b'\xff\xd8\xff',
    '.jpeg': b'\xff\xd8\xff',
}
TAMANO_MAXIMO_COMPROBANTE = 5 * 1024 * 1024  # 5 MB
AVISO_PAGO = (
    'Transferí el total a la cuenta que informe la administración y cargá el comprobante. '
    'El pago se considera acreditado solo cuando la administración lo aprueba.'
)


# --- Serialización -----------------------------------------------------------

def _dinero(valor):
    """Importes como texto con dos decimales: la app no pierde precisión."""
    return f'{Decimal(valor or 0):.2f}'


def _pagado(factura):
    total = factura.comprobantes.filter(estado='Aprobado').aggregate(suma=Sum('importe'))['suma']
    return total or Decimal('0')


def _alumno_dict(alumno):
    return {
        'legajo': alumno.legajo,
        'nombre': alumno.id_persona.nombre,
        'apellido': alumno.id_persona.apellido,
        'nivel': alumno.id_curso.nivel if alumno.id_curso_id else None,
    }


def _factura_dict(factura, pagado=None):
    pagado = _pagado(factura) if pagado is None else pagado
    return {
        'id': factura.id,
        'alumno': factura.alumno_id,
        'periodo': factura.periodo,
        'emision': factura.emision.isoformat(),
        'vencimiento': factura.vencimiento.isoformat(),
        'total': _dinero(factura.total),
        'pagado': _dinero(pagado),
        'saldo': _dinero(factura.total - pagado),
        'estado': factura.estado,
    }


def _item_dict(item):
    return {
        'id': item.id,
        'tipo': item.tipo,
        'descripcion': item.descripcion,
        'importe': _dinero(item.importe),
    }


def _comprobante_dict(comprobante):
    return {
        'id': comprobante.id,
        'importe': _dinero(comprobante.importe),
        'estado': comprobante.estado,
        'fecha_carga': comprobante.fecha_carga.isoformat(),
    }


def _cuota_dict(cuota):
    return {
        'id': cuota.id_cuota,
        'periodo': cuota.periodo,
        'monto': _dinero(cuota.monto),
        'estado': cuota.estado,
        'fecha_vencimiento': cuota.fecha_vencimiento.isoformat() if cuota.fecha_vencimiento else None,
        'fecha_pago': cuota.fecha_pago.isoformat() if cuota.fecha_pago else None,
        'medio_pago': cuota.medio_pago,
    }


def _solicitud_dict(solicitud):
    return {
        'id': solicitud.id,
        'factura': solicitud.factura_id,
        'total': _dinero(solicitud.total),
        'estado': solicitud.estado,
        'items': [_item_dict(item) for item in solicitud.items.all()],
        'aviso': AVISO_PAGO,
    }


# --- Helpers de acceso -------------------------------------------------------

def _alumno_de_query(request):
    """Lee ?alumno=<legajo> y verifica que el usuario pueda verlo."""
    legajo = request.query_params.get('alumno', '')
    if not legajo.isdigit():
        return None, Response(
            {'error': 'Indique el legajo del alumno con ?alumno=<legajo>.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return exigir_alumno_visible(request.user, int(legajo)), None


def _factura_visible(request, factura_id):
    factura = Factura.objects.select_related('alumno__id_persona', 'tutor__id_persona').filter(pk=factura_id).first()
    if factura is None:
        raise NotFound('Factura no encontrada.')
    exigir_alumno_visible(request.user, factura.alumno_id)
    return factura


def _fecha_query(request, nombre):
    valor = request.query_params.get(nombre)
    if not valor:
        return None
    try:
        return date.fromisoformat(valor)
    except ValueError:
        raise ValueError(f'{nombre} debe tener el formato AAAA-MM-DD.')


def _importe(valor):
    try:
        importe = Decimal(str(valor))
    except (InvalidOperation, TypeError):
        return None
    return importe if importe > 0 else None


def _validar_archivo(archivo):
    """Devuelve un mensaje de error, o None si el archivo es válido."""
    extension = os.path.splitext(archivo.name)[1].lower()
    if extension not in EXTENSIONES_COMPROBANTE:
        return 'Formato no permitido. Subí un PDF, PNG o JPG.'
    if archivo.size > TAMANO_MAXIMO_COMPROBANTE:
        return 'El archivo supera el máximo de 5 MB.'
    cabecera = archivo.read(8)
    archivo.seek(0)
    if not cabecera.startswith(EXTENSIONES_COMPROBANTE[extension]):
        return 'El contenido del archivo no coincide con su formato.'
    return None


# --- Consultas ----------------------------------------------------------------

@api_view(['GET'])
def alumnos(request):
    """Alumnos que el usuario puede consultar (sus hijos, o él mismo)."""
    lista = alumnos_visibles(request.user).select_related('id_persona', 'id_curso').order_by('id_persona__apellido')
    return Response([_alumno_dict(a) for a in lista])


@api_view(['GET'])
def cuotas(request):
    """Cuotas de un alumno. Filtro opcional: ?estado=Pendiente o ?estado=Pagada."""
    alumno, error = _alumno_de_query(request)
    if error:
        return error
    consulta = Cuota.objects.filter(id_legajo_alumno=alumno).order_by('-id_cuota')
    estado = request.query_params.get('estado')
    if estado:
        consulta = consulta.filter(estado=estado)
    return Response([_cuota_dict(c) for c in consulta])


@api_view(['GET'])
def deuda(request):
    """Deuda de un alumno, desglosada por factura e ítem."""
    alumno, error = _alumno_de_query(request)
    if error:
        return error

    facturas_con_saldo = Factura.objects.filter(alumno=alumno).exclude(estado='Pagada').order_by('periodo')
    total = Decimal('0')
    detalle = []
    for factura in facturas_con_saldo:
        pagado = _pagado(factura)
        total += factura.total - pagado
        detalle.append({
            **_factura_dict(factura, pagado),
            'items': [_item_dict(i) for i in factura.items.all()],
        })

    return Response({
        'alumno': _alumno_dict(alumno),
        'total_deuda': _dinero(total),
        'facturas': detalle,
    })


@api_view(['GET'])
def facturas(request):
    """Facturas y comprobantes visibles, con filtros ?alumno=, ?desde= y ?hasta= (AAAA-MM-DD)."""
    consulta = Factura.objects.select_related('alumno__id_persona').prefetch_related('comprobantes')
    consulta = consulta.filter(alumno__in=alumnos_visibles(request.user))

    if request.query_params.get('alumno'):
        alumno, error = _alumno_de_query(request)
        if error:
            return error
        consulta = consulta.filter(alumno=alumno)

    try:
        desde = _fecha_query(request, 'desde')
        hasta = _fecha_query(request, 'hasta')
    except ValueError as exc:
        return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    if desde:
        consulta = consulta.filter(emision__gte=desde)
    if hasta:
        consulta = consulta.filter(emision__lte=hasta)

    resultado = []
    for factura in consulta.order_by('-emision', '-id'):
        resultado.append({
            **_factura_dict(factura),
            'comprobantes': [_comprobante_dict(c) for c in factura.comprobantes.all()],
        })
    return Response(resultado)


@api_view(['GET'])
def factura_detalle(request, factura_id):
    factura = _factura_visible(request, factura_id)
    return Response({
        **_factura_dict(factura),
        'items': [_item_dict(i) for i in factura.items.all()],
        'comprobantes': [_comprobante_dict(c) for c in factura.comprobantes.all()],
    })


@api_view(['GET'])
def factura_pdf(request, factura_id):
    factura = _factura_visible(request, factura_id)
    respuesta = HttpResponse(generar_pdf_factura(factura), content_type='application/pdf')
    respuesta['Content-Disposition'] = f'inline; filename="factura-{factura.alumno_id}-{factura.periodo}.pdf"'
    return respuesta


# --- Pagos y comprobantes -----------------------------------------------------

@api_view(['POST'])
def crear_pago(request):
    """Solicitud de pago de ítems elegidos por el tutor. El total lo calcula el servidor.

    Requiere la cabecera Idempotency-Key: si la app reintenta, devuelve la misma solicitud.
    """
    exigir_rol(request.user, PADRE)

    clave = (request.headers.get('Idempotency-Key') or '').strip()
    if not clave or len(clave) > 64:
        return Response(
            {'error': 'Falta la cabecera Idempotency-Key (máximo 64 caracteres).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        factura_id = int(request.data.get('factura'))
        ids_items = [int(i) for i in request.data.get('items') or []]
    except (TypeError, ValueError):
        return Response({'error': 'Datos inválidos.'}, status=status.HTTP_400_BAD_REQUEST)
    if not ids_items:
        return Response({'error': 'Seleccione al menos un ítem.'}, status=status.HTTP_400_BAD_REQUEST)

    factura = _factura_visible(request, factura_id)

    previa = SolicitudPago.objects.filter(clave_idempotencia=clave).first()
    if previa is not None:
        if previa.factura_id != factura.id:
            return Response(
                {'error': 'Esa clave ya se usó para otra factura.'},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(_solicitud_dict(previa), status=status.HTTP_200_OK)

    if factura.estado == 'Pagada':
        return Response({'error': 'La factura ya está pagada.'}, status=status.HTTP_400_BAD_REQUEST)

    items = list(ItemFactura.objects.filter(factura=factura, pk__in=ids_items))
    if len(items) != len(set(ids_items)):
        return Response(
            {'error': 'Algún ítem no pertenece a esta factura.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        with transaction.atomic():
            solicitud = SolicitudPago.objects.create(
                factura=factura,
                total=sum((item.importe for item in items), Decimal('0')),
                clave_idempotencia=clave,
                creada_por=request.user,
            )
            solicitud.items.set(items)
    except IntegrityError:
        return Response(
            {'error': 'Ya existe una solicitud pendiente para esta factura.'},
            status=status.HTTP_409_CONFLICT,
        )

    return Response(_solicitud_dict(solicitud), status=status.HTTP_201_CREATED)


@api_view(['POST'])
def subir_comprobante(request, factura_id):
    """Carga el comprobante de la transferencia y lo asocia a la factura (RF-M05)."""
    exigir_rol(request.user, PADRE)
    factura = _factura_visible(request, factura_id)

    if factura.estado == 'Pagada':
        return Response({'error': 'La factura ya está pagada.'}, status=status.HTTP_400_BAD_REQUEST)

    archivo = request.FILES.get('archivo')
    if archivo is None:
        return Response({'error': 'Adjunte el comprobante en el campo "archivo".'}, status=status.HTTP_400_BAD_REQUEST)

    importe = _importe(request.data.get('importe'))
    if importe is None:
        return Response({'error': 'Indique un importe mayor a cero.'}, status=status.HTTP_400_BAD_REQUEST)

    error_archivo = _validar_archivo(archivo)
    if error_archivo:
        return Response({'error': error_archivo}, status=status.HTTP_400_BAD_REQUEST)

    comprobante = ComprobantePago.objects.create(
        factura=factura,
        archivo=archivo,
        importe=importe,
        subido_por=request.user,
    )
    return Response(_comprobante_dict(comprobante), status=status.HTTP_201_CREATED)


@api_view(['GET'])
def comprobante_archivo(request, comprobante_id):
    """Descarga el archivo de un comprobante, solo para quien puede ver ese alumno."""
    comprobante = ComprobantePago.objects.select_related('factura').filter(pk=comprobante_id).first()
    if comprobante is None:
        raise NotFound('Comprobante no encontrado.')
    exigir_alumno_visible(request.user, comprobante.factura.alumno_id)
    return FileResponse(comprobante.archivo.open('rb'), as_attachment=True, filename=os.path.basename(comprobante.archivo.name))
