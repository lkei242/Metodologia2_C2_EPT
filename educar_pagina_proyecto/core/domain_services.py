from dataclasses import dataclass
from functools import partial

from django.db import transaction

from .models import Alumno, AuditoriaCambio, GrupoDeportivo, InscripcionDeportiva
from .patterns import ConfiguracionTecnicaSingleton


class ReglaNegocioError(ValueError):
    """Error de validación del dominio que puede mostrarse al usuario."""


@dataclass(frozen=True)
class CambioConfirmado:
    usuario_id: int | None
    entidad: str
    registro_id: str
    accion: str
    campos: tuple[str, ...]


class AuditoriaObserver:
    def notificar(self, cambio: CambioConfirmado):
        AuditoriaCambio.objects.create(
            usuario_id=cambio.usuario_id,
            entidad=cambio.entidad,
            registro_id=cambio.registro_id,
            accion=cambio.accion,
            campos=list(cambio.campos),
        )


_AUDITORIA = AuditoriaObserver()


def publicar_cambio(request, entidad, registro_id, accion, campos):
    cambio = CambioConfirmado(
        usuario_id=request.session.get("usuario_id"),
        entidad=entidad,
        registro_id=str(registro_id),
        accion=accion,
        campos=tuple(sorted(set(campos))),
    )
    transaction.on_commit(partial(_AUDITORIA.notificar, cambio))


def inscribir_en_deporte(alumno_id, grupo_id, confirmar_migracion=False):
    with transaction.atomic():
        alumno = Alumno.objects.select_for_update().get(pk=alumno_id)
        grupo = GrupoDeportivo.objects.select_related("disciplina").get(pk=grupo_id)
        actuales = list(InscripcionDeportiva.objects.select_for_update().filter(alumno=alumno, estado="Activa").select_related("grupo"))

        legacy = alumno.id_disciplina_id
        grupos_actuales = {row.grupo_id for row in actuales}
        if any(row.grupo.disciplina_id == grupo.disciplina_id for row in actuales):
            raise ReglaNegocioError("El alumno ya participa en ese deporte.")
        if legacy and legacy != grupo.disciplina_id:
            raise ReglaNegocioError("El alumno tiene un deporte anterior sin horario estructurado; Administración debe revisarlo antes de asignar otro.")
        if legacy and not confirmar_migracion:
            raise ReglaNegocioError("Confirme con Administración el grupo y horario que representan la inscripción anterior.")
        limite = ConfiguracionTecnicaSingleton().get("max_deportes_por_alumno")
        deportes_existentes = len(actuales) if legacy else len(actuales)
        if deportes_existentes >= limite:
            raise ReglaNegocioError("El alumno no puede tener más de dos deportes activos.")

        for row in actuales:
            other = row.grupo
            if other.dia_semana == grupo.dia_semana and grupo.hora_inicio < other.hora_fin and grupo.hora_fin > other.hora_inicio:
                raise ReglaNegocioError(f"El horario se superpone con {other.disciplina.nombre} ({other.hora_inicio:%H:%M}-{other.hora_fin:%H:%M}).")
        if legacy:
            alumno.id_disciplina = None
            alumno.save(update_fields=["id_disciplina"])
        return InscripcionDeportiva.objects.create(alumno=alumno, grupo=grupo, estado="Activa")


def finalizar_deporte(alumno_id, inscripcion_id):
    with transaction.atomic():
        row = InscripcionDeportiva.objects.select_for_update().get(pk=inscripcion_id, alumno_id=alumno_id, estado="Activa")
        row.estado = "Finalizada"
        row.save(update_fields=["estado"])
        return row


def asignar_transporte(alumno_id, recorrido_id):
    from .models import Alumno, InscripcionTransporte
    with transaction.atomic():
        alumno = Alumno.objects.select_for_update().get(pk=alumno_id)
        actuales = list(InscripcionTransporte.objects.select_for_update().filter(alumno=alumno, estado="Activa"))
        if len(actuales) > 1:
            raise ReglaNegocioError("El alumno tiene más de un recorrido activo; se requiere revisión.")
        if actuales and (recorrido_id is None or actuales[0].recorrido_id != recorrido_id):
            actuales[0].estado = "Finalizada"
            actuales[0].save(update_fields=["estado"])
        if recorrido_id is not None and (not actuales or actuales[0].recorrido_id != recorrido_id):
            return InscripcionTransporte.objects.create(alumno=alumno, recorrido_id=recorrido_id, estado="Activa")
        return actuales[0] if actuales and recorrido_id is not None else None
