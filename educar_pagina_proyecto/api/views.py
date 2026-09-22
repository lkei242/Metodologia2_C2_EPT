"""API REST - Módulo 1: Autenticación para la aplicación móvil.

Reutiliza el modelo ``Usuario`` existente del sistema web, generando
tokens JWT para que la app móvil pueda autenticarse sin romper el login
por sesión que ya usa la web.
"""
import secrets
import string

from django.contrib.auth.hashers import check_password
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken

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


def _validar_contrasenia(usuario, password):
    """Acepta contraseñas en texto plano (login web actual) y hasheadas."""
    if usuario.contrasenia and usuario.contrasenia == password:
        return True
    return bool(usuario.contrasenia) and check_password(password, usuario.contrasenia)


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


@api_view(['POST'])
@permission_classes([AllowAny])
def recuperar_contrasena(request):
    """Genera una contraseña nueva, la guarda hasheada y la envía por correo."""
    identificador = (request.data.get('correo') or request.data.get('usuario') or '').strip()

    usuario = (
        Usuario.objects.filter(correo__iexact=identificador).first()
        or Usuario.objects.filter(nombre_usuario__iexact=identificador).first()
    )

    if not usuario:
        return Response(
            {'error': 'No se encontró una cuenta con ese correo o usuario.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    nueva = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
    usuario.contrasenia = nueva
    usuario.save(update_fields=['contrasenia'])

    destinatario = usuario.correo
    if destinatario:
        send_mail(
            subject='Recuperación de contraseña - Educar para Transformar',
            message=f'Hola {usuario.nombre_usuario}. Tu nueva contraseña es: {nueva}\n'
                    'Ingresá con ella y luego podés cambiarla desde tu perfil.',
            from_email=None,
            recipient_list=[destinatario],
            fail_silently=True,
        )

    return Response({
        'ok': True,
        'mensaje': 'Si la cuenta existe, recibirás una nueva contraseña por correo.',
    })


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