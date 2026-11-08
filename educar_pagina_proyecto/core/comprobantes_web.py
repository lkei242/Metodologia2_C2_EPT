"""Aprobación de comprobantes de transferencia desde la web (L13, D4).

Solo el personal administrativo puede aprobar o rechazar. Al aprobar, la factura
pasa a Parcial o Pagada según lo acreditado, y al quedar pagada se registra la
cuota en la tabla que usa el panel web.
"""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .domain_services import publicar_cambio
from .models import ComprobantePago, Cuota, Factura, SolicitudPago
from .views import requiere_roles

ROL_ADMIN = 'dashboard-administrativo'


@requiere_roles(ROL_ADMIN)
def comprobantes_pendientes(request):
    comprobantes = (
        ComprobantePago.objects.filter(estado='Pendiente')
        .select_related('factura__alumno__id_persona', 'factura__tutor__id_persona')
        .order_by('fecha_carga')
    )
    return render(request, 'core/comprobantes_pendientes.html', {'comprobantes': comprobantes})


@requiere_roles(ROL_ADMIN)
def comprobante_archivo_web(request, id_comprobante):
    comprobante = get_object_or_404(ComprobantePago, pk=id_comprobante)
    return FileResponse(comprobante.archivo.open('rb'), as_attachment=False)


def _recalcular_factura(factura, usuario_id):
    """Actualiza el estado de la factura según los comprobantes aprobados."""
    pagado = factura.comprobantes.filter(estado='Aprobado').aggregate(suma=Sum('importe'))['suma'] or Decimal('0')

    if pagado >= factura.total and factura.estado != 'Pagada':
        factura.estado = 'Pagada'
        factura.save(update_fields=['estado'])
        # Compatibilidad con el panel web: la cuota queda registrada como pagada.
        Cuota.objects.create(
            periodo=factura.periodo,
            monto=factura.total,
            fecha_pago=date.today(),
            medio_pago='Transferencia',
            estado='Pagada',
            id_tutor=factura.tutor,
            id_legajo_alumno=factura.alumno,
        )
        SolicitudPago.objects.filter(factura=factura, estado='Pendiente').update(estado='Pagada')
    elif pagado > 0 and factura.estado == 'Pendiente':
        factura.estado = 'Parcial'
        factura.save(update_fields=['estado'])


@require_POST
@requiere_roles(ROL_ADMIN)
def aprobar_comprobante(request, id_comprobante):
    with transaction.atomic():
        comprobante = ComprobantePago.objects.select_for_update().select_related('factura').get(pk=id_comprobante)
        if comprobante.estado != 'Pendiente':
            messages.error(request, 'Ese comprobante ya fue revisado.', extra_tags='comprobantes')
            return redirect('comprobantes-pendientes')

        comprobante.estado = 'Aprobado'
        comprobante.save(update_fields=['estado'])
        _recalcular_factura(comprobante.factura, request.session.get('usuario_id'))
        publicar_cambio(request, 'ComprobantePago', comprobante.pk, 'aprobar', ['estado'])

    messages.success(request, 'Comprobante aprobado.', extra_tags='comprobantes')
    return redirect('comprobantes-pendientes')


@require_POST
@requiere_roles(ROL_ADMIN)
def rechazar_comprobante(request, id_comprobante):
    with transaction.atomic():
        comprobante = ComprobantePago.objects.select_for_update().get(pk=id_comprobante)
        if comprobante.estado != 'Pendiente':
            messages.error(request, 'Ese comprobante ya fue revisado.', extra_tags='comprobantes')
            return redirect('comprobantes-pendientes')

        comprobante.estado = 'Rechazado'
        comprobante.save(update_fields=['estado'])
        publicar_cambio(request, 'ComprobantePago', comprobante.pk, 'rechazar', ['estado'])

    messages.success(request, 'Comprobante rechazado.', extra_tags='comprobantes')
    return redirect('comprobantes-pendientes')
