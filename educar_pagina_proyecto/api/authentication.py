"""Autenticación JWT personalizada sobre el modelo ``Usuario`` existente.

SimpleJWT espera por defecto el modelo ``AUTH_USER_MODEL`` de Django.
Como el sistema usa un modelo propio (``core.Usuario``), esta clase decodifica
el token con ``AccessToken`` y resuelve el usuario desde ese modelo.
"""
from rest_framework import authentication, exceptions
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

from core.models import Usuario


class UsuarioJWTAuthentication(authentication.BaseAuthentication):
    def authenticate(self, request):
        header = request.headers.get('Authorization')
        if not header or not header.startswith('Bearer '):
            return None

        token = header.split(' ', 1)[1].strip()
        try:
            decoded = AccessToken(token)
        except TokenError:
            raise exceptions.AuthenticationFailed('Token inválido o expirado.')

        try:
            usuario = Usuario.objects.get(id=decoded['user_id'])
        except (Usuario.DoesNotExist, KeyError):
            raise exceptions.AuthenticationFailed('Usuario no encontrado.')

        return (usuario, None)

    def authenticate_header(self, request):
        return 'Bearer'