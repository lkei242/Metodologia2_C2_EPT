"""Permisos personalizados para la API.

``core.Usuario`` no tiene el atributo ``is_authenticated`` que DRF espera;
esta clase considera autenticado a cualquier usuario resuelto (por JWT o
sesión) y rechaza a ``AnonymousUser``.
"""
from rest_framework.permissions import BasePermission


class EsAutenticado(BasePermission):
    def has_permission(self, request, view):
        if not request.user:
            return False
        return bool(getattr(request.user, 'is_authenticated', True))