"""API REST - Módulo de Servicios (RF-M16, RF-M17, RF-M18).

Permite la consulta y gestión de inscripciones a deportes, recorridos de transporte
y comedor escolar para la aplicación móvil, asegurando validaciones de rol,
pertenencia tutor-alumno y reglas de negocio del dominio.
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response

from api.authentication import UsuarioJWTAuthentication
from api.permissions import EsAutenticado
from core.domain_services import (
    ReglaNegocioError,
    asignar_transporte,
    finalizar_deporte,
    gestionar_comedor,
    inscribir_en_deporte,
    publicar_cambio,
)
from core.models import (
    Alumno,
    Directivo,
    Docente,
    GrupoDeportivo,
    InscripcionDeportiva,
    InscripcionTransporte,
    Noticia,
    Persona,
    PersonalAdministrativo,
    Preceptor,
    RecorridoTransporte,
    Tutor,
    TutorTutoraAlumno,
)


def _obtener_rol_usuario(usuario):
    persona = Persona.objects.filter(id_usuario=usuario).first()
    if not persona:
        return None, None
    if PersonalAdministrativo.objects.filter(id_persona=persona).exists():
        return 'administrativo', persona
    if Tutor.objects.filter(id_persona=persona).exists():
        return 'padre', persona
    if Alumno.objects.filter(id_persona=persona).exists():
        return 'alumno', persona
    if Directivo.objects.filter(id_persona=persona).exists():
        return 'directivo', persona
    if Docente.objects.filter(id_persona=persona).exists():
        return 'docente', persona
    if Preceptor.objects.filter(id_persona=persona).exists():
        return 'preceptor', persona
    return None, persona


def _obtener_alumnos_autorizados(usuario):
    """Devuelve el queryset de Alumnos que este usuario puede consultar/gestionar."""
    rol, persona = _obtener_rol_usuario(usuario)
    if rol in ('administrativo', 'directivo', 'docente', 'preceptor'):
        return Alumno.objects.filter(estado='Activo')
    if rol == 'padre':
        tutor = Tutor.objects.filter(id_persona=persona).first()
        if not tutor:
            return Alumno.objects.none()
        return Alumno.objects.filter(tutortutoraalumno__id_tutor=tutor, estado='Activo').distinct()
    if rol == 'alumno':
        return Alumno.objects.filter(id_persona=persona, estado='Activo')
    return Alumno.objects.none()


def _verificar_acceso_alumno(usuario, alumno_id):
    """Verifica que el usuario tenga permiso sobre el alumno dado y lo devuelve."""
    alumnos = _obtener_alumnos_autorizados(usuario)
    alumno = alumnos.filter(pk=alumno_id).select_related('id_persona', 'id_curso').first()
    return alumno


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def listar_alumnos(request):
    """Devuelve los alumnos que el usuario autenticado tiene autorizados a ver."""
    alumnos = _obtener_alumnos_autorizados(request.user).select_related('id_persona', 'id_curso')
    data = []
    for a in alumnos:
        data.append({
            'id': a.pk,
            'legajo': a.legajo,
            'nombre': a.id_persona.nombre,
            'apellido': a.id_persona.apellido,
            'dni': a.id_persona.dni,
            'curso': str(a.id_curso) if a.id_curso else 'Sin curso asignado',
            'inscripto_comedor': a.inscripto_comedor,
        })
    return Response(data)


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def mis_servicios(request):
    """Devuelve los servicios activos (deportes, transporte, comedor) de un alumno."""
    alumno_id = request.query_params.get('alumno')
    if not alumno_id:
        rol, persona = _obtener_rol_usuario(request.user)
        if rol == 'alumno':
            propio = Alumno.objects.filter(id_persona=persona).first()
            if propio:
                alumno_id = propio.pk

    if not alumno_id:
        return Response(
            {'error': 'Debe especificar el parámetro alumno con el ID del alumno.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    alumno = _verificar_acceso_alumno(request.user, alumno_id)
    if not alumno:
        return Response(
            {'error': 'No tiene permisos para acceder a los datos de este alumno.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Deportes activos
    inscripciones_dep = InscripcionDeportiva.objects.filter(
        alumno=alumno, estado='Activa'
    ).select_related('grupo__disciplina', 'grupo__profesor_responsable__id_persona')

    deportes = []
    for ins in inscripciones_dep:
        g = ins.grupo
        prof = g.profesor_responsable.id_persona if g.profesor_responsable else None
        deportes.append({
            'inscripcion_id': ins.pk,
            'grupo_id': g.pk,
            'disciplina': g.disciplina.nombre,
            'nivel': g.nivel,
            'dia_semana': g.dia_semana,
            'hora_inicio': g.hora_inicio.strftime('%H:%M') if g.hora_inicio else '',
            'hora_fin': g.hora_fin.strftime('%H:%M') if g.hora_fin else '',
            'profesor': f"{prof.nombre} {prof.apellido}" if prof else 'A confirmar',
            'fecha_inscripcion': ins.fecha_inscripcion.strftime('%Y-%m-%d') if ins.fecha_inscripcion else '',
        })

    # Transporte activo
    ins_trans = InscripcionTransporte.objects.filter(
        alumno=alumno, estado='Activa'
    ).select_related('recorrido').first()

    transporte = None
    if ins_trans and ins_trans.recorrido:
        transporte = {
            'inscripcion_id': ins_trans.pk,
            'recorrido_id': ins_trans.recorrido.pk,
            'nombre': ins_trans.recorrido.nombre,
            'descripcion': ins_trans.recorrido.descripcion,
            'fecha_inscripcion': ins_trans.fecha_inscripcion.strftime('%Y-%m-%d') if ins_trans.fecha_inscripcion else '',
        }

    return Response({
        'alumno': {
            'id': alumno.pk,
            'legajo': alumno.legajo,
            'nombre': alumno.id_persona.nombre,
            'apellido': alumno.id_persona.apellido,
            'curso': str(alumno.id_curso) if alumno.id_curso else '',
        },
        'deportes': deportes,
        'transporte': transporte,
        'comedor': alumno.inscripto_comedor,
    })


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def listar_grupos_deportivos(request):
    """Catálogo de grupos deportivos disponibles con horarios y docentes."""
    grupos = GrupoDeportivo.objects.select_related(
        'disciplina', 'profesor_responsable__id_persona'
    ).order_by('disciplina__nombre', 'nivel', 'dia_semana', 'hora_inicio')

    data = []
    for g in grupos:
        prof = g.profesor_responsable.id_persona if g.profesor_responsable else None
        data.append({
            'id': g.pk,
            'disciplina_id': g.disciplina.pk,
            'disciplina': g.disciplina.nombre,
            'nivel': g.nivel,
            'dia_semana': g.dia_semana,
            'hora_inicio': g.hora_inicio.strftime('%H:%M') if g.hora_inicio else '',
            'hora_fin': g.hora_fin.strftime('%H:%M') if g.hora_fin else '',
            'profesor': f"{prof.nombre} {prof.apellido}" if prof else 'Sin asignar',
        })
    return Response(data)


@api_view(['POST'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def inscribir_deporte(request):
    """Inscribe a un alumno en un grupo deportivo validando máximos y horarios."""
    alumno_id = request.data.get('alumno_id')
    grupo_id = request.data.get('grupo_id')

    if not alumno_id or not grupo_id:
        return Response(
            {'error': 'Debe proveer alumno_id y grupo_id.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    alumno = _verificar_acceso_alumno(request.user, alumno_id)
    if not alumno:
        return Response(
            {'error': 'No tiene permisos para inscribir a este alumno.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        ins = inscribir_en_deporte(alumno_id=alumno.pk, grupo_id=grupo_id)
        publicar_cambio(
            request.user,
            'InscripcionDeportiva',
            ins.pk,
            'inscribir',
            ['alumno', 'grupo', 'estado'],
        )
    except GrupoDeportivo.DoesNotExist:
        return Response(
            {'error': 'El grupo deportivo solicitado no existe.'},
            status=status.HTTP_404_NOT_FOUND,
        )
    except ReglaNegocioError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return Response({
        'ok': True,
        'mensaje': 'Inscripción deportiva registrada con éxito.',
        'inscripcion_id': ins.pk,
    }, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def desinscribir_deporte(request, inscripcion_id):
    """Finaliza/cancela la inscripción de un alumno a un deporte."""
    ins = InscripcionDeportiva.objects.filter(pk=inscripcion_id).first()
    if not ins:
        return Response(
            {'error': 'No se encontró la inscripción especificada.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    alumno = _verificar_acceso_alumno(request.user, ins.alumno_id)
    if not alumno:
        return Response(
            {'error': 'No tiene permisos para modificar la inscripción de este alumno.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        finalizar_deporte(alumno_id=alumno.pk, inscripcion_id=ins.pk)
        publicar_cambio(
            request.user,
            'InscripcionDeportiva',
            ins.pk,
            'finalizar',
            ['estado'],
        )
    except ReglaNegocioError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'ok': True, 'mensaje': 'Inscripción deportiva finalizada correctamente.'})


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def listar_recorridos_transporte(request):
    """Devuelve los recorridos de transporte activos."""
    recorridos = RecorridoTransporte.objects.filter(activo=True).order_by('nombre')
    data = [
        {
            'id': r.pk,
            'nombre': r.nombre,
            'descripcion': r.descripcion,
            'activo': r.activo,
        }
        for r in recorridos
    ]
    return Response(data)


@api_view(['PUT'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def actualizar_transporte(request):
    """Asigna, cambia o cancela el recorrido de transporte de un alumno."""
    alumno_id = request.data.get('alumno_id')
    recorrido_id = request.data.get('recorrido_id')  # Puede ser None para retirar

    if not alumno_id:
        return Response(
            {'error': 'Debe especificar alumno_id.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    alumno = _verificar_acceso_alumno(request.user, alumno_id)
    if not alumno:
        return Response(
            {'error': 'No tiene permisos para gestionar el transporte de este alumno.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    if recorrido_id is not None:
        if not RecorridoTransporte.objects.filter(pk=recorrido_id, activo=True).exists():
            return Response(
                {'error': 'El recorrido de transporte seleccionado no existe o no está activo.'},
                status=status.HTTP_404_NOT_FOUND,
            )

    try:
        ins = asignar_transporte(alumno_id=alumno.pk, recorrido_id=recorrido_id)
        publicar_cambio(
            request.user,
            'InscripcionTransporte',
            ins.pk if ins else alumno.pk,
            'asignar' if ins else 'retirar',
            ['alumno', 'recorrido'],
        )
    except ReglaNegocioError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    mensaje = 'Recorrido de transporte asignado correctamente.' if ins else 'Servicio de transporte retirado.'
    return Response({
        'ok': True,
        'mensaje': mensaje,
        'inscripcion_id': ins.pk if ins else None,
        'recorrido_id': recorrido_id,
    })


@api_view(['PUT'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def actualizar_comedor(request):
    """Activa o desactiva la inscripción al comedor escolar."""
    alumno_id = request.data.get('alumno_id')
    inscripto = request.data.get('inscripto')

    if alumno_id is None or inscripto is None:
        return Response(
            {'error': 'Debe proveer alumno_id e inscripto (booleano).'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    alumno = _verificar_acceso_alumno(request.user, alumno_id)
    if not alumno:
        return Response(
            {'error': 'No tiene permisos para modificar el comedor de este alumno.'},
            status=status.HTTP_403_FORBIDDEN,
        )

    alumno_actualizado = gestionar_comedor(alumno.pk, bool(inscripto))
    publicar_cambio(
        request.user,
        'Alumno',
        alumno.pk,
        'comedor',
        ['inscripto_comedor'],
    )

    estado_txt = 'activado' if alumno_actualizado.inscripto_comedor else 'desactivado'
    return Response({
        'ok': True,
        'inscripto_comedor': alumno_actualizado.inscripto_comedor,
        'mensaje': f'Servicio de comedor {estado_txt} correctamente.',
    })


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def paquete_offline(request):
    """Devuelve un paquete consolidado de datos para consulta offline (RF-M17)."""
    usuario = request.user
    rol, persona = _obtener_rol_usuario(usuario)
    alumnos = _obtener_alumnos_autorizados(usuario).select_related('id_persona', 'id_curso')

    alumnos_data = []
    for a in alumnos:
        # Deportes activos
        ins_deps = InscripcionDeportiva.objects.filter(
            alumno=a, estado='Activa'
        ).select_related('grupo__disciplina', 'grupo__profesor_responsable__id_persona')
        deps = []
        for ins in ins_deps:
            prof = ins.grupo.profesor_responsable.id_persona if ins.grupo.profesor_responsable else None
            deps.append({
                'inscripcion_id': ins.pk,
                'disciplina': ins.grupo.disciplina.nombre,
                'nivel': ins.grupo.nivel,
                'dia_semana': ins.grupo.dia_semana,
                'horario': f"{ins.grupo.hora_inicio.strftime('%H:%M')} - {ins.grupo.hora_fin.strftime('%H:%M')}",
                'profesor': f"{prof.nombre} {prof.apellido}" if prof else 'Sin asignar',
            })

        # Transporte
        trans = None
        ins_t = InscripcionTransporte.objects.filter(alumno=a, estado='Activa').select_related('recorrido').first()
        if ins_t and ins_t.recorrido:
            trans = {
                'recorrido_id': ins_t.recorrido.pk,
                'nombre': ins_t.recorrido.nombre,
                'descripcion': ins_t.recorrido.descripcion,
            }

        alumnos_data.append({
            'id': a.pk,
            'legajo': a.legajo,
            'nombre': f"{a.id_persona.nombre} {a.id_persona.apellido}",
            'dni': a.id_persona.dni,
            'curso': str(a.id_curso) if a.id_curso else '',
            'comedor': a.inscripto_comedor,
            'deportes': deps,
            'transporte': trans,
        })

    # Catálogo de grupos deportivos
    grupos_db = GrupoDeportivo.objects.select_related(
        'disciplina', 'profesor_responsable__id_persona'
    ).order_by('disciplina__nombre', 'dia_semana')
    grupos_catalogo = []
    for g in grupos_db:
        prof = g.profesor_responsable.id_persona if g.profesor_responsable else None
        grupos_catalogo.append({
            'id': g.pk,
            'disciplina': g.disciplina.nombre,
            'nivel': g.nivel,
            'dia_semana': g.dia_semana,
            'horario': f"{g.hora_inicio.strftime('%H:%M')} - {g.hora_fin.strftime('%H:%M')}",
            'profesor': f"{prof.nombre} {prof.apellido}" if prof else 'Sin asignar',
        })

    # Recorridos de transporte
    recorridos_catalogo = [
        {'id': r.pk, 'nombre': r.nombre, 'descripcion': r.descripcion}
        for r in RecorridoTransporte.objects.filter(activo=True)
    ]

    # Noticias / Comunicados institucionales
    noticias_db = Noticia.objects.order_by('-fecha_publicacion')[:10]
    noticias_data = []
    for n in noticias_db:
        noticias_data.append({
            'id': n.pk,
            'titulo': n.titulo,
            'contenido': n.contenido,
            'fecha': n.fecha_publicacion.strftime('%Y-%m-%d') if n.fecha_publicacion else '',
        })

    return Response({
        'sincronizado_en': timezone.now().isoformat(),
        'usuario': {
            'username': usuario.nombre_usuario,
            'correo': usuario.correo,
            'rol': rol,
            'persona': {
                'nombre': persona.nombre if persona else '',
                'apellido': persona.apellido if persona else '',
                'dni': persona.dni if persona else '',
                'email': persona.email if persona else '',
                'telefono': persona.telefono if persona else '',
            } if persona else None,
        },
        'alumnos': alumnos_data,
        'catalogo_deportes': grupos_catalogo,
        'catalogo_transporte': recorridos_catalogo,
        'comunicados': noticias_data,
    })
