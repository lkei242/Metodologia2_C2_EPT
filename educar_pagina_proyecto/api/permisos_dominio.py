"""Roles y pertenencia de datos, compartidos por la API de pagos y servicios.

El rol sale siempre del servidor (según las tablas de Persona), nunca de lo que
manda la app. Un tutor solo accede a sus hijos vinculados; un alumno, a sí mismo.
"""
from rest_framework.exceptions import PermissionDenied

from core.models import (
    Alumno,
    Directivo,
    Docente,
    Persona,
    PersonalAdministrativo,
    Preceptor,
    Tutor,
    TutorTutoraAlumno,
)

ADMINISTRATIVO = 'administrativo'
DIRECTIVO = 'directivo'
DOCENTE = 'docente'
PRECEPTOR = 'preceptor'
PADRE = 'padre'
ALUMNO = 'alumno'


ROLES_PERSONAL_ESCOLAR = (ADMINISTRATIVO, DIRECTIVO, DOCENTE, PRECEPTOR)


def persona_de(usuario):
    return Persona.objects.filter(id_usuario=usuario).first()


def rol_de(usuario):
    """Devuelve el rol del usuario, o None si no tiene persona asociada."""
    persona = persona_de(usuario)
    if persona is None:
        return None
    if PersonalAdministrativo.objects.filter(id_persona=persona).exists():
        return ADMINISTRATIVO
    if Docente.objects.filter(id_persona=persona).exists():
        return DOCENTE
    if Tutor.objects.filter(id_persona=persona).exists():
        return PADRE
    if Preceptor.objects.filter(id_persona=persona).exists():
        return PRECEPTOR
    if Directivo.objects.filter(id_persona=persona).exists():
        return DIRECTIVO
    if Alumno.objects.filter(id_persona=persona).exists():
        return ALUMNO
    return None


def exigir_rol(usuario, *roles):
    """Corta con 403 si el rol del usuario no está entre los permitidos."""
    rol = rol_de(usuario)
    if rol not in roles:
        raise PermissionDenied('Su rol no puede realizar esta acción.')
    return rol


def hijos_visibles(usuario):
    """Alumnos vinculados al tutor autenticado."""
    tutor = Tutor.objects.filter(id_persona__id_usuario=usuario).first()
    if tutor is None:
        return Alumno.objects.none()
    ids = TutorTutoraAlumno.objects.filter(id_tutor=tutor).values('id_alumno')
    return Alumno.objects.filter(pk__in=ids)


def alumnos_visibles(usuario):
    """Alumnos cuyos datos financieros puede consultar el usuario."""
    rol = rol_de(usuario)
    if rol in ROLES_PERSONAL_ESCOLAR:
        return Alumno.objects.all()
    if rol == PADRE:
        return hijos_visibles(usuario)
    if rol == ALUMNO:
        return Alumno.objects.filter(id_persona__id_usuario=usuario)
    return Alumno.objects.none()


def exigir_alumno_visible(usuario, legajo):
    """Devuelve el alumno si el usuario puede verlo; si no, corta con 403."""
    alumno = alumnos_visibles(usuario).filter(pk=legajo).first()
    if alumno is None:
        raise PermissionDenied('No tiene acceso a este alumno.')
    return alumno
