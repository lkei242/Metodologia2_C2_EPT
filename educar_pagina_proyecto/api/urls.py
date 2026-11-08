from django.urls import include, path

from . import views

urlpatterns = [
    path('login/', views.login, name='api-login'),
    path('login/refresh/', views.login_renovar_token, name='api-login-refresh'),
    path('logout/', views.logout, name='api-logout'),
    path('recuperar-contrasena/', views.recuperar_contrasena, name='api-recuperar-contrasena'),
    path('recuperar-contrasena/confirmar/', views.recuperar_contrasena_confirmar, name='api-recuperar-contrasena-confirmar'),
    path('perfil/', views.perfil, name='api-perfil'),
    # Módulos: pagos y facturación (Luka) y servicios (Germán)
    path('', include('api.urls_pagos')),
    path('servicios/', include('api.urls_servicios')),
]