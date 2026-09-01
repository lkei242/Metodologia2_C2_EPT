from .models import (
    Usuario,
    Persona,
    PersonalAdministrativo,
    Docente,
    Tutor,
    Preceptor,
    Directivo,
    Alumno,
)


def datos_sesion_context(request):
    """Context processor de Django que provee automáticamente la información
    del usuario autenticado ('persona') y la URL del panel de control ('dashboard_url')
    a todas las plantillas.

    Esto elimina la duplicación de código en las funciones de vista.
    """
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return {'persona': None, 'dashboard_url': None}

    try:
        usuario = Usuario.objects.get(id=usuario_id)
        persona = Persona.objects.filter(id_usuario=usuario).first()
        if not persona:
            return {'persona': None, 'dashboard_url': None}

        dashboard_url = 'login'
        if PersonalAdministrativo.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-administrativo'
        elif Docente.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-docente'
        elif Tutor.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-padres'
        elif Preceptor.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-preceptor'
        elif Directivo.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-directivo'
        elif Alumno.objects.filter(id_persona=persona).exists():
            dashboard_url = 'dashboard-alumno'

        return {'persona': persona, 'dashboard_url': dashboard_url}
    except Usuario.DoesNotExist:
        return {'persona': None, 'dashboard_url': None}
