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


def alumnos_de_docente(usuario):
    """Alumnos de los cursos donde el docente dicta alguna materia (igual que su panel web)."""
    docente = Docente.objects.filter(id_persona__id_usuario=usuario).first()
    if docente is None:
        return Alumno.objects.none()
    return Alumno.objects.filter(
        id_curso__cursocursamaterias__id_materia__docentedictamateria__id_docente=docente,
    ).distinct()


def alumnos_de_preceptor(usuario):
    """Alumnos de los cursos asignados al preceptor (igual que su panel web)."""
    preceptor = Preceptor.objects.filter(id_persona__id_usuario=usuario).first()
    if preceptor is None:
        return Alumno.objects.none()
    return Alumno.objects.filter(id_curso__legajo_preceptor=preceptor)


def alumnos_visibles(usuario):
    """Alumnos que el usuario puede consultar.

    Administrativo y directivo ven a todos; el docente y el preceptor, solo a los alumnos de sus
    cursos (lo mismo que ven en la web); el tutor, a sus hijos; el alumno, a sí mismo.
    """
    rol = rol_de(usuario)
    if rol in (ADMINISTRATIVO, DIRECTIVO):
        return Alumno.objects.all()
    if rol == DOCENTE:
        return alumnos_de_docente(usuario)
    if rol == PRECEPTOR:
        return alumnos_de_preceptor(usuario)
    if rol == PADRE:
        return hijos_visibles(usuario)
    if rol == ALUMNO:
        return Alumno.objects.filter(id_persona__id_usuario=usuario)
    return Alumno.objects.none()


# El docente y el preceptor no tienen datos financieros en la web, así que tampoco en la app.
ROLES_SIN_FINANZAS = (DOCENTE, PRECEPTOR)


def alumnos_visibles_finanzas(usuario):
    """Alumnos cuyos datos financieros (cuotas, deuda, facturas) puede consultar el usuario."""
    if rol_de(usuario) in ROLES_SIN_FINANZAS:
        return Alumno.objects.none()
    return alumnos_visibles(usuario)


def exigir_alumno_visible(usuario, legajo):
    """Devuelve el alumno si el usuario puede ver sus datos financieros; si no, corta con 403."""
    alumno = alumnos_visibles_finanzas(usuario).filter(pk=legajo).first()
    if alumno is None:
        raise PermissionDenied('No tiene acceso a este alumno.')
    return alumno
