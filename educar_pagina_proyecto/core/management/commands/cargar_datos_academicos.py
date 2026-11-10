"""Completa asistencias y notas de demostración para los alumnos que no tienen ninguna.

Pensado para que los paneles (alumno, tutor, preceptor, directivo) tengan datos en toda
la institución durante una demostración. Es aditivo y repetible:

* solo carga a los alumnos activos, con curso, que NO tienen registros de ese tipo;
* nunca modifica ni borra registros existentes;
* si se ejecuta dos veces, la segunda no agrega nada;
* los valores son deterministas (cada alumno recibe siempre los mismos).

Uso:
    python manage.py cargar_datos_academicos --dry-run      # muestra qué haría
    python manage.py cargar_datos_academicos --confirmar    # carga los datos

Haga una copia de db.sqlite3 antes de ejecutarlo sobre datos reales: las notas no tienen
una marca que permita distinguirlas después de las cargadas por los docentes.
"""
import random
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import Alumno, Asistencia, Calificacion, CursoCursaMaterias

BIMESTRES = ("1° Bimestre", "2° Bimestre", "3° Bimestre")
# Mes y día en que se cierra cada bimestre (se acotan a "hoy" si todavía no llegaron).
CIERRE_BIMESTRE = ((5, 15), (7, 17), (9, 18))
LOTE = 500


def dias_habiles_hasta_ayer(cantidad, hoy):
    """Los últimos `cantidad` días de lunes a viernes anteriores a hoy, en orden cronológico."""
    dias = []
    dia = hoy - timedelta(days=1)
    while len(dias) < cantidad:
        if dia.weekday() < 5:
            dias.append(dia)
        dia -= timedelta(days=1)
    return sorted(dias)


def nota_de_demostracion(legajo, id_materia, indice_bimestre):
    """Nota de 2,0 a 10,0 con un decimal. Cada alumno tiene un nivel propio y varía por materia."""
    nivel = random.Random(f"nivel-{legajo}").uniform(5.0, 9.0)
    variacion = random.Random(f"{legajo}-{id_materia}-{indice_bimestre}").gauss(0, 1.1)
    return Decimal(str(round(min(10.0, max(2.0, nivel + variacion)), 1)))


def asistencia_de_demostracion(legajo, fecha):
    """'Presente', 'Tardanza' o 'Ausente'; la mayoría presente, con perfiles distintos por alumno."""
    probabilidad_presente = random.Random(f"asistencia-{legajo}").uniform(0.84, 0.98)
    sorteo = random.Random(f"{legajo}-{fecha.isoformat()}").random()
    if sorteo < probabilidad_presente:
        return "Presente"
    if sorteo < probabilidad_presente + (1 - probabilidad_presente) * 0.4:
        return "Tardanza"
    return "Ausente"


class Command(BaseCommand):
    help = "Carga asistencias y notas de demostración para los alumnos que no tienen ninguna."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Muestra qué se cargaría sin guardar nada.")
        parser.add_argument("--confirmar", action="store_true", help="Confirma que quiere escribir en la base de datos.")
        parser.add_argument("--dias", type=int, default=15, help="Días hábiles de asistencia a cargar (1 a 60). Por defecto 15.")
        parser.add_argument("--bimestres", type=int, choices=(1, 2, 3), default=2, help="Cantidad de bimestres con nota. Por defecto 2.")
        parser.add_argument("--omitir-notas", action="store_true", help="No cargar notas.")
        parser.add_argument("--omitir-asistencias", action="store_true", help="No cargar asistencias.")

    def handle(self, *args, **options):
        simulacion = options["dry_run"]
        if not simulacion and not options["confirmar"]:
            raise CommandError(
                "Este comando escribe datos en la base. Ejecútelo con --dry-run para ver qué haría "
                "o con --confirmar para cargarlos (haga antes una copia de db.sqlite3)."
            )
        if not 1 <= options["dias"] <= 60:
            raise CommandError("--dias debe estar entre 1 y 60.")

        hoy = date.today()
        alumnos = list(
            Alumno.objects.filter(estado="Activo", id_curso__isnull=False).only("legajo", "id_curso_id")
        )
        self.stdout.write(f"Alumnos activos con curso: {len(alumnos)}")

        with transaction.atomic():
            notas = 0 if options["omitir_notas"] else self._cargar_notas(alumnos, options["bimestres"], hoy)
            asistencias = 0 if options["omitir_asistencias"] else self._cargar_asistencias(alumnos, options["dias"], hoy)
            if simulacion:
                transaction.set_rollback(True)

        etiqueta = "Se cargarían" if simulacion else "Cargados"
        self.stdout.write(self.style.SUCCESS(f"{etiqueta}: {notas} notas y {asistencias} asistencias."))
        if simulacion:
            self.stdout.write("Simulación: no se guardó nada.")

    def _cargar_notas(self, alumnos, cantidad_bimestres, hoy):
        con_notas = set(Calificacion.objects.values_list("legajo_alumno_id", flat=True).distinct())
        materias_por_curso = defaultdict(list)
        for id_curso, id_materia in CursoCursaMaterias.objects.values_list("id_curso_id", "id_materia_id"):
            materias_por_curso[id_curso].append(id_materia)

        fechas = [min(date(hoy.year, mes, dia), hoy) for mes, dia in CIERRE_BIMESTRE[:cantidad_bimestres]]
        faltantes = [a for a in alumnos if a.legajo not in con_notas]
        sin_materias = sum(1 for a in faltantes if not materias_por_curso.get(a.id_curso_id))
        self.stdout.write(
            f"Notas: {len(faltantes)} alumnos sin notas"
            + (f" ({sin_materias} omitidos porque su curso no tiene materias)" if sin_materias else "")
        )

        nuevas = []
        for alumno in faltantes:
            for id_materia in materias_por_curso.get(alumno.id_curso_id, []):
                for indice, fecha in enumerate(fechas):
                    nuevas.append(Calificacion(
                        legajo_alumno_id=alumno.legajo,
                        id_materia_id=id_materia,
                        tipo_evaluacion=BIMESTRES[indice],
                        nota=nota_de_demostracion(alumno.legajo, id_materia, indice),
                        fecha=fecha,
                    ))
        Calificacion.objects.bulk_create(nuevas, batch_size=LOTE)
        return len(nuevas)

    def _cargar_asistencias(self, alumnos, cantidad_dias, hoy):
        con_asistencia = set(Asistencia.objects.values_list("legajo_alumno_id", flat=True).distinct())
        faltantes = [a for a in alumnos if a.legajo not in con_asistencia]
        self.stdout.write(f"Asistencias: {len(faltantes)} alumnos sin registros")

        dias = dias_habiles_hasta_ayer(cantidad_dias, hoy)
        nuevas = [
            Asistencia(
                legajo_alumno_id=alumno.legajo,
                fecha=dia,
                tipo_asistencia=asistencia_de_demostracion(alumno.legajo, dia),
            )
            for alumno in faltantes
            for dia in dias
        ]
        Asistencia.objects.bulk_create(nuevas, batch_size=LOTE)
        return len(nuevas)
