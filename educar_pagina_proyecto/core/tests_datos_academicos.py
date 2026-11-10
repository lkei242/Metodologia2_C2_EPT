"""Pruebas del comando cargar_datos_academicos."""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .management.commands.cargar_datos_academicos import (
    asistencia_de_demostracion, dias_habiles_hasta_ayer, nota_de_demostracion,
)
from .models import Alumno, Asistencia, Calificacion, Curso, CursoCursaMaterias, Materia, Persona


class CargarDatosAcademicosTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nivel="Primario", anio=3, comision="A", turno="Mañana")
        self.curso_sin_materias = Curso.objects.create(nivel="Primario", anio=4, comision="A", turno="Mañana")
        self.materias = [
            Materia.objects.create(nombre=nombre, descripcion="", carga_horaria=2, cantidad_clases=30)
            for nombre in ("Matemática", "Lengua", "Arte")
        ]
        for materia in self.materias:
            CursoCursaMaterias.objects.create(id_curso=self.curso, id_materia=materia, horarios="")
        self.con_datos = self.crear_alumno("40000001")
        self.sin_datos = self.crear_alumno("40000002")
        self.otro_sin_datos = self.crear_alumno("40000003")

    def crear_alumno(self, dni, curso=None, estado="Activo"):
        persona = Persona.objects.create(dni=dni, nombre="Ana", apellido=dni, fecha_nacimiento=date(2016, 1, 1))
        return Alumno.objects.create(id_persona=persona, id_curso=curso or self.curso, estado=estado)

    def ejecutar(self, *argumentos):
        salida = StringIO()
        call_command("cargar_datos_academicos", *argumentos, stdout=salida)
        return salida.getvalue()

    def test_sin_confirmar_ni_simular_no_escribe_y_explica_por_que(self):
        with self.assertRaisesMessage(CommandError, "--confirmar"):
            self.ejecutar()
        self.assertEqual(Calificacion.objects.count() + Asistencia.objects.count(), 0)

    def test_dry_run_informa_cuanto_cargaria_y_no_guarda_nada(self):
        salida = self.ejecutar("--dry-run")
        self.assertIn("Se cargarían", salida)
        self.assertIn("no se guardó nada", salida)
        self.assertEqual(Calificacion.objects.count() + Asistencia.objects.count(), 0)

    def test_carga_solo_a_los_alumnos_que_no_tienen_registros(self):
        nota_previa = Calificacion.objects.create(
            legajo_alumno=self.con_datos, id_materia=self.materias[0], nota=Decimal("7.0"),
            tipo_evaluacion="Oral", fecha=date(2026, 9, 1),
        )
        asistencia_previa = Asistencia.objects.create(
            legajo_alumno=self.con_datos, fecha=date(2026, 9, 1), tipo_asistencia="Presente",
        )
        self.ejecutar("--confirmar", "--dias", "10", "--bimestres", "2")

        # El alumno que ya tenía datos queda intacto.
        self.assertEqual(Calificacion.objects.filter(legajo_alumno=self.con_datos).count(), 1)
        self.assertEqual(Asistencia.objects.filter(legajo_alumno=self.con_datos).count(), 1)
        nota_previa.refresh_from_db()
        asistencia_previa.refresh_from_db()
        self.assertEqual(nota_previa.nota, Decimal("7.0"))

        # Los otros reciben 3 materias x 2 bimestres y 10 días hábiles.
        for alumno in (self.sin_datos, self.otro_sin_datos):
            self.assertEqual(Calificacion.objects.filter(legajo_alumno=alumno).count(), 6)
            self.assertEqual(Asistencia.objects.filter(legajo_alumno=alumno).count(), 10)

    def test_se_puede_ejecutar_dos_veces_sin_duplicar(self):
        self.ejecutar("--confirmar")
        notas, asistencias = Calificacion.objects.count(), Asistencia.objects.count()
        salida = self.ejecutar("--confirmar")
        self.assertEqual((Calificacion.objects.count(), Asistencia.objects.count()), (notas, asistencias))
        self.assertIn("0 notas y 0 asistencias", salida)

    def test_las_notas_tienen_el_formato_que_leen_los_paneles(self):
        self.ejecutar("--confirmar", "--bimestres", "3")
        tipos = set(Calificacion.objects.values_list("tipo_evaluacion", flat=True))
        self.assertEqual(tipos, {"1° Bimestre", "2° Bimestre", "3° Bimestre"})
        for calificacion in Calificacion.objects.all():
            self.assertTrue(Decimal("2.0") <= calificacion.nota <= Decimal("10.0"))
            self.assertEqual(calificacion.nota, calificacion.nota.quantize(Decimal("0.1")))
            self.assertLessEqual(calificacion.fecha, date.today())
        # Un mismo alumno y materia no repite bimestre (como exige la pantalla del docente).
        repetidas = (
            Calificacion.objects.values("legajo_alumno", "id_materia", "tipo_evaluacion").distinct().count()
        )
        self.assertEqual(repetidas, Calificacion.objects.count())

    def test_las_asistencias_son_dias_habiles_pasados_y_con_estado_valido(self):
        self.ejecutar("--confirmar", "--dias", "12")
        fechas = set(Asistencia.objects.values_list("fecha", flat=True))
        self.assertEqual(len(fechas), 12)
        for fecha in fechas:
            self.assertLess(fecha, date.today(), "No debe cargar el día de hoy")
            self.assertLess(fecha.weekday(), 5, "No debe cargar fines de semana")
        estados = set(Asistencia.objects.values_list("tipo_asistencia", flat=True))
        self.assertTrue(estados <= {"Presente", "Tardanza", "Ausente"})
        self.assertIn("Presente", estados)

    def test_omite_alumnos_inactivos_y_cursos_sin_materias_en_las_notas(self):
        inactivo = self.crear_alumno("40000004", estado="Inactivo")
        sin_materias = self.crear_alumno("40000005", curso=self.curso_sin_materias)
        self.ejecutar("--confirmar")
        self.assertFalse(Calificacion.objects.filter(legajo_alumno=inactivo).exists())
        self.assertFalse(Asistencia.objects.filter(legajo_alumno=inactivo).exists())
        self.assertFalse(Calificacion.objects.filter(legajo_alumno=sin_materias).exists())
        self.assertTrue(Asistencia.objects.filter(legajo_alumno=sin_materias).exists())

    def test_se_puede_cargar_solo_notas_o_solo_asistencias(self):
        self.ejecutar("--confirmar", "--omitir-asistencias")
        self.assertTrue(Calificacion.objects.exists())
        self.assertFalse(Asistencia.objects.exists())
        Calificacion.objects.all().delete()
        self.ejecutar("--confirmar", "--omitir-notas")
        self.assertFalse(Calificacion.objects.exists())
        self.assertTrue(Asistencia.objects.exists())

    def test_los_datos_son_deterministas(self):
        self.assertEqual(nota_de_demostracion(5, 2, 0), nota_de_demostracion(5, 2, 0))
        fecha = date(2026, 9, 10)
        self.assertEqual(asistencia_de_demostracion(5, fecha), asistencia_de_demostracion(5, fecha))
        self.ejecutar("--confirmar")
        primera = list(Calificacion.objects.order_by("id_calificacion").values_list("nota", flat=True))
        Calificacion.objects.all().delete()
        self.ejecutar("--confirmar", "--omitir-asistencias")
        segunda = list(Calificacion.objects.order_by("id_calificacion").values_list("nota", flat=True))
        self.assertEqual(primera, segunda)

    def test_rechaza_una_cantidad_de_dias_fuera_de_rango(self):
        for dias in ("0", "61"):
            with self.assertRaises(CommandError):
                self.ejecutar("--confirmar", "--dias", dias)

    def test_dias_habiles_hasta_ayer_salta_los_fines_de_semana(self):
        lunes = date(2026, 11, 9)
        dias = dias_habiles_hasta_ayer(3, lunes)
        self.assertEqual(dias, [date(2026, 11, 4), date(2026, 11, 5), date(2026, 11, 6)])
