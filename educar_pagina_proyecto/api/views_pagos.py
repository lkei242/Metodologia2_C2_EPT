"""API de cuotas, deuda, facturas, pagos y comprobantes.

Cubre RF-M03 a RF-M07. Todas las vistas validan rol y pertenencia del dato en el
servidor: un tutor solo ve a sus hijos, un alumno solo a sí mismo.
"""
import os
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import IntegrityError, transaction
from django.db.models import Q, Sum
from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

from api.permisos_dominio import (
    DOCENTE,
    PADRE,
    PRECEPTOR,
    alumnos_visibles,
    alumnos_visibles_finanzas,
    exigir_alumno_visible,
    exigir_rol,
    rol_de,
)
from core.facturacion import generar_pdf_factura
from core.models import ComprobantePago, Cuota, Factura, ItemFactura, SolicitudPago, TutorTutoraAlumno

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


def _alumno_dict(alumno, reducido=False):
    """Datos del alumno. `reducido` quita domicilio, teléfono, correo y datos del tutor.

    Se usa para el docente y el preceptor, que en la web no ven esos datos.
    """
    persona = alumno.id_persona
    curso = alumno.id_curso
    rel_tutor = (
        TutorTutoraAlumno.objects.filter(id_alumno=alumno)
        .select_related('id_tutor__id_persona')
        .first()
    )
    tutor_dict = None
    if rel_tutor and rel_tutor.id_tutor:
        tp = rel_tutor.id_tutor.id_persona
        tutor_dict = {
            'nombre': f"{tp.nombre} {tp.apellido}" if tp else "No asignado",
            'parentesco': rel_tutor.tipo_parentesco or "Tutor",
            'telefono': rel_tutor.id_tutor.telefono_contacto or (tp.telefono if tp else "") or "",
            'email': rel_tutor.id_tutor.email_contacto or (tp.email if tp else "") or "",
        }
    return {
        'legajo': alumno.legajo,
        'nombre': persona.nombre,
        'apellido': persona.apellido,
        'dni': persona.dni or "",
        'fecha_nacimiento': persona.fecha_nacimiento.isoformat() if persona.fecha_nacimiento else None,
        'telefono': "" if reducido else (persona.telefono or ""),
        'email': "" if reducido else (persona.email or ""),
        'direccion': "" if reducido else (persona.direccion or ""),
        'estado': alumno.estado,
        'fecha_ingreso': alumno.fecha_ingreso.isoformat() if alumno.fecha_ingreso else None,
        'inscripto_comedor': bool(alumno.inscripto_comedor),
        'curso': f"{curso.anio}° {curso.comision}" if curso else "Sin asignar",
        'anio': curso.anio if curso else None,
        'comision': curso.comision if curso else None,
        'nivel': curso.nivel if curso else None,
        'turno': curso.turno if curso else None,
        'tutor': None if reducido else tutor_dict,
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
    """Alumnos que el usuario puede consultar (personal escolar ve todos; tutor ve sus hijos; alumno se ve a sí mismo).

    Admite filtros opcionales por query params:
    - ?q= : búsqueda parcial por nombre, apellido, dni o legajo
    - ?nivel= : Inicial, Primario, Secundario
    - ?anio= : año del curso (ej: 1, 2, 3...)
    - ?turno= : Mañana, Tarde, Vespertino
    - ?estado= : Activo, Inactivo
    - ?fecha_nacimiento= : AAAA-MM-DD
    - ?anio_nacimiento= : AAAA (ej: 2012)
    - ?nacimiento_desde= : AAAA-MM-DD
    - ?nacimiento_hasta= : AAAA-MM-DD
    - ?comedor= : 1 / true / 0 / false
    """
    qs = (
        alumnos_visibles(request.user)
        .select_related('id_persona', 'id_curso')
        .prefetch_related('tutortutoraalumno_set__id_tutor__id_persona')
        .order_by('id_persona__apellido', 'id_persona__nombre')
    )

    q = request.query_params.get('q', '').strip()
    if q:
        filtro_q = (
            Q(id_persona__nombre__icontains=q)
            | Q(id_persona__apellido__icontains=q)
            | Q(id_persona__dni__icontains=q)
        )
        if q.isdigit():
            filtro_q |= Q(legajo=int(q))
        qs = qs.filter(filtro_q)

    nivel = request.query_params.get('nivel', '').strip()
    if nivel and nivel.lower() != 'todos':
        qs = qs.filter(id_curso__nivel__iexact=nivel)

    anio = request.query_params.get('anio', '').strip()
    if anio and anio.isdigit():
        qs = qs.filter(id_curso__anio=int(anio))

    turno = request.query_params.get('turno', '').strip()
    if turno and turno.lower() != 'todos':
        qs = qs.filter(id_curso__turno__iexact=turno)

    estado = request.query_params.get('estado', '').strip()
    if estado and estado.lower() != 'todos':
        qs = qs.filter(estado__iexact=estado)

    fnac = request.query_params.get('fecha_nacimiento', '').strip()
    if fnac:
        try:
            fecha_obj = date.fromisoformat(fnac)
            qs = qs.filter(id_persona__fecha_nacimiento=fecha_obj)
        except ValueError:
            pass

    anio_nac = request.query_params.get('anio_nacimiento', '').strip()
    if anio_nac and anio_nac.isdigit():
        qs = qs.filter(id_persona__fecha_nacimiento__year=int(anio_nac))

    nac_desde = request.query_params.get('nacimiento_desde', '').strip()
    if nac_desde:
        try:
            d = date.fromisoformat(nac_desde)
            qs = qs.filter(id_persona__fecha_nacimiento__gte=d)
        except ValueError:
            pass

    nac_hasta = request.query_params.get('nacimiento_hasta', '').strip()
    if nac_hasta:
        try:
            h = date.fromisoformat(nac_hasta)
            qs = qs.filter(id_persona__fecha_nacimiento__lte=h)
        except ValueError:
            pass

    comedor = request.query_params.get('comedor', '').strip().lower()
    if comedor in ('1', 'true', 'si', 'sí'):
        qs = qs.filter(inscripto_comedor=True)
    elif comedor in ('0', 'false', 'no'):
        qs = qs.filter(inscripto_comedor=False)

    reducido = rol_de(request.user) in (DOCENTE, PRECEPTOR)
    return Response([_alumno_dict(a, reducido=reducido) for a in qs])


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
    consulta = consulta.filter(alumno__in=alumnos_visibles_finanzas(request.user))

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
