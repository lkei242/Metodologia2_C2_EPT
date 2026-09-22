from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.login, name='api-login'),
    path('login/refresh/', views.login_renovar_token, name='api-login-refresh'),
    path('logout/', views.logout, name='api-logout'),
    path('recuperar-contrasena/', views.recuperar_contrasena, name='api-recuperar-contrasena'),
    path('perfil/', views.perfil, name='api-perfil'),
]