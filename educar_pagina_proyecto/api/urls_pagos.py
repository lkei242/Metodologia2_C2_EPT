"""Rutas de cuotas, deuda, facturas, pagos y comprobantes (Luka).

Se incluyen desde api/urls.py bajo /api/.
"""
from django.urls import path

from . import views_pagos as v

urlpatterns = [
    path('alumnos/', v.alumnos, name='api-alumnos'),
    path('cuotas/', v.cuotas, name='api-cuotas'),
    path('deuda/', v.deuda, name='api-deuda'),
    path('facturas/', v.facturas, name='api-facturas'),
    path('facturas/<int:factura_id>/', v.factura_detalle, name='api-factura-detalle'),
    path('facturas/<int:factura_id>/pdf/', v.factura_pdf, name='api-factura-pdf'),
    path('facturas/<int:factura_id>/comprobantes/', v.subir_comprobante, name='api-subir-comprobante'),
    path('comprobantes/<int:comprobante_id>/archivo/', v.comprobante_archivo, name='api-comprobante-archivo'),
    path('pagos/', v.crear_pago, name='api-pagos'),
]
