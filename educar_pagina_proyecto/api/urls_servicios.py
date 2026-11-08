"""Rutas de la API para Servicios (RF-M16, RF-M17).

Gestionadas por Germán.
"""
from django.urls import path

from . import views_servicios

urlpatterns = [
    path('alumnos/', views_servicios.listar_alumnos, name='api-servicios-alumnos'),
    path('mis-servicios/', views_servicios.mis_servicios, name='api-servicios-mis-servicios'),
    path('deportes/grupos/', views_servicios.listar_grupos_deportivos, name='api-servicios-deportes-grupos'),
    path('deportes/inscripciones/', views_servicios.inscribir_deporte, name='api-servicios-deportes-inscribir'),
    path('deportes/inscripciones/<int:inscripcion_id>/', views_servicios.desinscribir_deporte, name='api-servicios-deportes-desinscribir'),
    path('transporte/recorridos/', views_servicios.listar_recorridos_transporte, name='api-servicios-transporte-recorridos'),
    path('transporte/inscripcion/', views_servicios.actualizar_transporte, name='api-servicios-transporte-inscripcion'),
    path('comedor/', views_servicios.actualizar_comedor, name='api-servicios-comedor'),
    path('offline-bundle/', views_servicios.paquete_offline, name='api-servicios-offline-bundle'),
]
