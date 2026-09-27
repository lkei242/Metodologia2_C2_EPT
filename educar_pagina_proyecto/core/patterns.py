from types import MappingProxyType

from django.conf import settings


class ConfiguracionTecnicaSingleton:
    """Instancia única, inmutable y solo para configuración técnica del proceso."""
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            instancia = super().__new__(cls)
            object.__setattr__(instancia, "_valores", MappingProxyType({
                "max_deportes_por_alumno": 2,
                "max_recorridos_transporte": 4,
                "modo_debug": bool(settings.DEBUG),
            }))
            cls._instancia = instancia
        return cls._instancia

    def __setattr__(self, nombre, valor):
        raise AttributeError("La configuración técnica es inmutable")

    def get(self, clave):
        return self._valores[clave]


class DjangoReportesAdapter:
    """Traduce el esquema Django heredado a consultas consistentes para los reportes."""
    def alumnos(self):
        from .models import Alumno
        return Alumno.objects.select_related("id_persona", "id_curso", "id_disciplina")

    def asignaciones_docentes(self):
        from .models import DocenteCursoMateria
        return DocenteCursoMateria.objects.select_related("docente__id_persona", "curso", "materia")

    def inscripciones_deportivas(self):
        from .models import InscripcionDeportiva
        return InscripcionDeportiva.objects.filter(estado="Activa").select_related("alumno__id_persona", "alumno__id_curso", "grupo__disciplina", "grupo__profesor_responsable__id_persona")

    def inscripciones_transporte(self):
        from .models import InscripcionTransporte
        return InscripcionTransporte.objects.filter(estado="Activa").select_related("alumno__id_persona", "alumno__id_curso", "recorrido")
