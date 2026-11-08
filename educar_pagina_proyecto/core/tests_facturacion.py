"""Pruebas de facturación mensual (Luka, L9)."""
from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from .facturacion import FacturacionError, calcular_items, generar_factura, generar_pdf_factura, vencimiento_para
from .models import (
    Alumno,
    Arancel,
    DisciplinaDeportiva,
    Docente,
    Factura,
    GrupoDeportivo,
    Inscripcion,
    InscripcionDeportiva,
    InscripcionTransporte,
    Instalacion,
    Persona,
    RecorridoTransporte,
    Curso,
    Tutor,
    TutorTutoraAlumno,
    ValorComedor,
)


class FacturacionTests(TestCase):
    def setUp(self):
        self.curso = Curso.objects.create(nivel="Primario", anio=1, comision="A", turno="Mañana")
        Arancel.objects.create(nivel="Primario", monto=Decimal("10000.00"))

        persona_tutor = Persona.objects.create(dni="40000001", nombre="Tutor", apellido="Uno", fecha_nacimiento=date(1980, 1, 1))
        self.tutor = Tutor.objects.create(id_persona=persona_tutor)
        persona = Persona.objects.create(dni="50000001", nombre="Hijo", apellido="Uno", fecha_nacimiento=date(2015, 1, 1))
        self.alumno = Alumno.objects.create(id_persona=persona, id_curso=self.curso, estado="Activo")
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.alumno)

        persona_docente = Persona.objects.create(dni="30000001", nombre="Profe", apellido="Uno", fecha_nacimiento=date(1980, 1, 1))
        self.docente = Docente.objects.create(id_persona=persona_docente, titulo="Profesor")
        self.instalacion = Instalacion.objects.create(nombre="Gimnasio", capacidad=30, estado="Activo")

    def deporte(self, nombre, valor):
        disciplina = DisciplinaDeportiva.objects.create(nombre=nombre, id_instalacion=self.instalacion, valor=valor)
        grupo = GrupoDeportivo.objects.create(
            disciplina=disciplina, nivel="Primario", dia_semana="Lunes",
            hora_inicio="08:00", hora_fin="09:00", profesor_responsable=self.docente,
        )
        InscripcionDeportiva.objects.create(alumno=self.alumno, grupo=grupo)

    def test_factura_incluye_cuota_servicios_y_total(self):
        self.deporte("Fútbol", Decimal("3000.00"))
        RecorridoTransporte.objects.create(nombre="Ruta 1", valor=Decimal("5000.00"))
        InscripcionTransporte.objects.create(alumno=self.alumno, recorrido=RecorridoTransporte.objects.get(nombre="Ruta 1"))
        ValorComedor.objects.create(monto=Decimal("2000.00"))
        self.alumno.inscripto_comedor = True
        self.alumno.save()

        factura, creada = generar_factura(self.alumno, "2026-11", date(2026, 11, 1))

        self.assertTrue(creada)
        self.assertEqual(factura.total, Decimal("20000.00"))
        tipos = sorted(factura.items.values_list("tipo", flat=True))
        self.assertEqual(tipos, ["comedor", "cuota", "deporte", "transporte"])

    def test_no_duplica_la_factura_del_periodo(self):
        generar_factura(self.alumno, "2026-11", date(2026, 11, 1))
        _, creada = generar_factura(self.alumno, "2026-11", date(2026, 11, 2))
        self.assertFalse(creada)
        self.assertEqual(Factura.objects.count(), 1)

    def test_falla_si_un_deporte_no_tiene_valor(self):
        self.deporte("Natación", None)
        with self.assertRaises(FacturacionError):
            calcular_items(self.alumno)

    def test_falla_si_no_hay_arancel_para_el_nivel(self):
        Arancel.objects.all().delete()
        with self.assertRaises(FacturacionError):
            generar_factura(self.alumno, "2026-11")

    def test_vencimiento_es_el_diez_del_mes_siguiente(self):
        self.assertEqual(vencimiento_para("2026-11"), date(2026, 12, 10))
        self.assertEqual(vencimiento_para("2026-12"), date(2027, 1, 10))

    def test_periodo_invalido_se_rechaza(self):
        with self.assertRaises(FacturacionError):
            generar_factura(self.alumno, "2026-13")

    def test_pdf_de_factura(self):
        factura, _ = generar_factura(self.alumno, "2026-11", date(2026, 11, 1))
        self.assertTrue(generar_pdf_factura(factura).startswith(b"%PDF"))

    def test_comando_genera_facturas_del_periodo(self):
        salida = StringIO()
        call_command("generar_facturas", "--periodo", "2026-11", stdout=salida)
        self.assertEqual(Factura.objects.filter(periodo="2026-11").count(), 1)
        self.assertIn("1 facturas creadas", salida.getvalue())
