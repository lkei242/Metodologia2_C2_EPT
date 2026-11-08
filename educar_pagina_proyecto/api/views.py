"""API REST - Módulo 1: Autenticación para la aplicación móvil.

Reutiliza el modelo ``Usuario`` existente del sistema web, generando
tokens JWT para que la app móvil pueda autenticarse sin romper el login
por sesión que ya usa la web.

Las contraseñas se guardan con hash (core.seguridad) y la recuperación no
envía ninguna contraseña: manda un token de un solo uso que vence en 30 minutos.
"""
import hashlib

from django.contrib.auth.password_validation import validate_password
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.authentication import UsuarioJWTAuthentication
from api.permissions import EsAutenticado
from core.models import (
    Alumno,
    Directivo,
    Docente,
    Persona,
    PersonalAdministrativo,
    Preceptor,
    Tutor,
    Usuario,
)
from core.seguridad import guardar_contrasenia, verificar_contrasenia

SALT_RECUPERACION = 'api.recuperacion-contrasena'
VIGENCIA_RECUPERACION = 30 * 60  # segundos
MENSAJE_RECUPERACION = 'Si la cuenta existe, te enviamos por correo las instrucciones para recuperarla.'


def _rol_dashboard(persona):
    """Devuelve (rol, dashboard_url) de una Persona, o (None, 'login')."""
    if not persona:
        return None, 'login'
    if PersonalAdministrativo.objects.filter(id_persona=persona).exists():
        return 'administrativo', 'dashboard-administrativo'
    if Docente.objects.filter(id_persona=persona).exists():
        return 'docente', 'dashboard-docente'
    if Tutor.objects.filter(id_persona=persona).exists():
        return 'padre', 'dashboard-padres'
    if Preceptor.objects.filter(id_persona=persona).exists():
        return 'preceptor', 'dashboard-preceptor'
    if Directivo.objects.filter(id_persona=persona).exists():
        return 'directivo', 'dashboard-directivo'
    if Alumno.objects.filter(id_persona=persona).exists():
        return 'alumno', 'dashboard-alumno'
    return None, 'login'


def _datos_persona(persona):
    if not persona:
        return None
    return {
        'id': persona.id,
        'nombre': persona.nombre,
        'apellido': persona.apellido,
        'dni': persona.dni,
        'email': persona.email,
        'telefono': persona.telefono,
    }


def _validar_contrasenia(usuario, password):
    """Verifica la contraseña contra el hash guardado."""
    return verificar_contrasenia(usuario, password)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    """Autentica usuario/correo + contraseña y devuelve tokens JWT + rol."""
    usuario_input = (request.data.get('usuario') or request.data.get('correo') or '').strip()
    password = request.data.get('password')

    if not usuario_input or not password:
        return Response(
            {'error': 'Debe ingresar usuario y contraseña.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    usuario = (
        Usuario.objects.filter(nombre_usuario=usuario_input).first()
        or Usuario.objects.filter(correo=usuario_input).first()
    )

    if not usuario or not _validar_contrasenia(usuario, password):
        return Response(
            {'error': 'Datos incorrectos'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    persona = Persona.objects.filter(id_usuario=usuario).first()
    rol, dashboard_url = _rol_dashboard(persona)

    refresh = RefreshToken()
    refresh['user_id'] = usuario.id
    refresh['nombre_usuario'] = usuario.nombre_usuario

    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'usuario': usuario.nombre_usuario,
        'correo': usuario.correo,
        'rol': rol,
        'dashboard_url': dashboard_url,
        'persona': _datos_persona(persona),
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def login_renovar_token(request):
    """Renueva el token de acceso usando el refresh token."""
    refresh = request.data.get('refresh')
    if not refresh:
        return Response(
            {'error': 'Debe enviar el refresh token.'},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        token = RefreshToken(refresh)
        return Response({'access': str(token.access_token)})
    except TokenError:
        return Response(
            {'error': 'Refresh token inválido o expirado.'},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def logout(request):
    """Invalida el refresh token (lo agrega a la lista negra)."""
    refresh = request.data.get('refresh')
    if refresh:
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            pass
    return Response({'ok': True})


def _huella(usuario):
    """Cambia cuando cambia la contraseña: así cada token sirve una sola vez."""
    return hashlib.sha256((usuario.contrasenia or '').encode()).hexdigest()[:16]


def _token_recuperacion(usuario):
    return signing.dumps({'uid': usuario.id, 'h': _huella(usuario)}, salt=SALT_RECUPERACION)


def _usuario_por_token(token):
    """Devuelve el usuario si el token es válido, vigente y no fue usado."""
    try:
        datos = signing.loads(token, salt=SALT_RECUPERACION, max_age=VIGENCIA_RECUPERACION)
    except signing.BadSignature:
        return None
    usuario = Usuario.objects.filter(id=datos.get('uid')).first()
    if usuario is None or _huella(usuario) != datos.get('h'):
        return None
    return usuario


@api_view(['POST'])
@permission_classes([AllowAny])
def recuperar_contrasena(request):
    """Envía un token de recuperación por correo.

    Responde lo mismo exista o no la cuenta, para no revelar qué usuarios hay.
    """
    identificador = (request.data.get('correo') or request.data.get('usuario') or '').strip()

    usuario = None
    if identificador:
        usuario = (
            Usuario.objects.filter(correo__iexact=identificador).first()
            or Usuario.objects.filter(nombre_usuario__iexact=identificador).first()
        )

    if usuario and usuario.correo:
        send_mail(
            subject='Recuperación de contraseña - Educar para Transformar',
            message=(
                f'Hola {usuario.nombre_usuario}.\n\n'
                'Para recuperar tu contraseña, ingresá este código en la app. '
                'Vence en 30 minutos y solo se puede usar una vez:\n\n'
                f'{_token_recuperacion(usuario)}\n\n'
                'Si no fuiste vos, ignorá este mensaje.'
            ),
            from_email=None,
            recipient_list=[usuario.correo],
            fail_silently=True,
        )

    return Response({'ok': True, 'mensaje': MENSAJE_RECUPERACION})


@api_view(['POST'])
@permission_classes([AllowAny])
def recuperar_contrasena_confirmar(request):
    """Cambia la contraseña usando el token recibido por correo."""
    token = (request.data.get('token') or '').strip()
    nueva = request.data.get('nueva') or ''

    usuario = _usuario_por_token(token) if token else None
    if usuario is None:
        return Response(
            {'error': 'El código no es válido o ya venció.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        validate_password(nueva)
    except ValidationError as exc:
        return Response({'error': ' '.join(exc.messages)}, status=status.HTTP_400_BAD_REQUEST)

    usuario.contrasenia = guardar_contrasenia(nueva)
    usuario.save(update_fields=['contrasenia'])
    return Response({'ok': True, 'mensaje': 'Contraseña actualizada. Ya podés iniciar sesión.'})


@api_view(['GET'])
@authentication_classes([UsuarioJWTAuthentication])
@permission_classes([EsAutenticado])
def perfil(request):
    """Devuelve los datos del usuario autenticado (identificado por el token)."""
    usuario = request.user
    persona = Persona.objects.filter(id_usuario=usuario).first()
    rol, dashboard_url = _rol_dashboard(persona)

    return Response({
        'usuario': usuario.nombre_usuario,
        'correo': usuario.correo,
        'rol': rol,
        'dashboard_url': dashboard_url,
        'persona': _datos_persona(persona),
    })
