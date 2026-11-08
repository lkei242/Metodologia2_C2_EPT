"""Contraseñas: se guardan siempre con hash de Django, nunca en texto plano.

La web y la API usan estas mismas funciones para crear y verificar contraseñas.
"""
from django.contrib.auth.hashers import check_password, identify_hasher, make_password


def es_hash(valor):
    """True si el valor ya es un hash reconocido por Django."""
    if not valor:
        return False
    try:
        identify_hasher(valor)
    except ValueError:
        return False
    return True


def guardar_contrasenia(texto):
    """Devuelve el hash que se guarda en Usuario.contrasenia."""
    return make_password(texto)


def verificar_contrasenia(usuario, texto):
    """Compara el texto ingresado con el hash del usuario.

    Un valor que no sea hash (texto plano heredado) nunca autentica: la
    migración 0005 convierte esos valores antes de que la app entre en uso.
    """
    if not texto or not es_hash(usuario.contrasenia):
        return False
    return check_password(texto, usuario.contrasenia)
