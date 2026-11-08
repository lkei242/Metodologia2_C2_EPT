"""Servicio institucional de correos automáticos (RF-M08, RF-M09).

Maneja el envío de recordatorios de pago del último día hábil y los avisos de deuda
del día 20, con desglose, registro de envíos y reintentos.
"""
import datetime
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, send_mail
from django.utils import timezone

from .models import Alumno, AuditoriaCambio, Tutor, TutorTutoraAlumno


def registrar_envio_correo(tutor_id, tipo, destinatario, estado, detalle=""):
    """Registra el evento de envío o reintento de correo en la auditoría del sistema."""
    AuditoriaCambio.objects.create(
        usuario=None,
        entidad="CorreoNotificacion",
        registro_id=str(tutor_id or "sistema"),
        accion=f"correo_{tipo}_{estado}",
        campos=[tipo, destinatario, estado, detalle, timezone.now().isoformat()],
    )


def enviar_recordatorio_ultimo_dia_habil(fecha_referencia=None):
    """Envía al tutor el recordatorio de pago con desglose de servicios (RF-M08)."""
    fecha = fecha_referencia or datetime.date.today()
    tutores = Tutor.objects.select_related("id_persona__id_usuario").all()

    enviados = 0
    fallidos = 0

    for tutor in tutores:
        persona = tutor.id_persona
        destinatario = persona.email or (persona.id_usuario.correo if persona.id_usuario else None)
        if not destinatario:
            continue

        hijos = Alumno.objects.filter(tutortutoraalumno__id_tutor=tutor, estado="Activo").select_related(
            "id_persona", "id_curso"
        )
        if not hijos.exists():
            continue

        lineas_hijos = []
        for h in hijos:
            comedor_txt = "Sí" if h.inscripto_comedor else "No"
            lineas_hijos.append(f"- {h.id_persona.nombre} {h.id_persona.apellido} ({h.id_curso or 'Sin curso'}) · Comedor: {comedor_txt}")

        detalle_alumnos = "\n".join(lineas_hijos)

        asunto = f"Recordatorio de pago - Cuota escolar ({fecha.strftime('%m/%Y')})"
        cuerpo = (
            f"Estimado/a {persona.nombre} {persona.apellido}:\n\n"
            f"Le recordamos que hoy es el último día hábil para el pago regular del arancel escolar mensual correspondiente a {fecha.strftime('%B %Y')}.\n\n"
            f"Alumnos a cargo:\n{detalle_alumnos}\n\n"
            f"Para consultar el desglose exacto o subir su comprobante de transferencia bancaria, acceda a la app móvil de Matech o a la plataforma web institucional.\n\n"
            f"Atentamente,\nAdministración - Centro Educativo Educar para Transformar"
        )

        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[destinatario],
                fail_silently=False,
            )
            registrar_envio_correo(tutor.pk, "recordatorio", destinatario, "exito")
            enviados += 1
        except Exception as exc:
            registrar_envio_correo(tutor.pk, "recordatorio", destinatario, "reintento_fallido", str(exc))
            fallidos += 1

    return {"fecha": str(fecha), "enviados": enviados, "fallidos": fallidos}


def enviar_aviso_deuda_dia_20(fecha_referencia=None):
    """Envía el día 20 el aviso de deuda a tutores con saldo pendiente (RF-M09)."""
    fecha = fecha_referencia or datetime.date.today()
    tutores = Tutor.objects.select_related("id_persona__id_usuario").all()

    enviados = 0
    fallidos = 0

    for tutor in tutores:
        persona = tutor.id_persona
        destinatario = persona.email or (persona.id_usuario.correo if persona.id_usuario else None)
        if not destinatario:
            continue

        hijos = Alumno.objects.filter(tutortutoraalumno__id_tutor=tutor, estado="Activo").select_related("id_persona")
        if not hijos.exists():
            continue

        asunto = "Aviso de Regularización de Deuda - Educar para Transformar"
        cuerpo = (
            f"Estimado/a {persona.nombre} {persona.apellido}:\n\n"
            f"Le informamos que al día 20 del corriente mes se registran aranceles pendientes de pago asociados a su grupo familiar.\n\n"
            f"Le solicitamos regularizar la situación mediante transferencia bancaria y subir el comprobante a través de la aplicación móvil para su imputación administrativa.\n\n"
            f"Ante cualquier consulta o dificultad, comuníquese con Administración.\n\n"
            f"Atentamente,\nDepartamento de Cobranzas - Educar para Transformar"
        )

        try:
            send_mail(
                subject=asunto,
                message=cuerpo,
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                recipient_list=[destinatario],
                fail_silently=False,
            )
            registrar_envio_correo(tutor.pk, "aviso_deuda", destinatario, "exito")
            enviados += 1
        except Exception as exc:
            registrar_envio_correo(tutor.pk, "aviso_deuda", destinatario, "reintento_fallido", str(exc))
            fallidos += 1

    return {"fecha": str(fecha), "enviados": enviados, "fallidos": fallidos}
