"""Pruebas de qué alumnos y datos ven el docente y el preceptor en la API de la app móvil.

Deben ver lo mismo que en su panel web: solo los alumnos de sus cursos, sin domicilio ni datos del
tutor, sin datos financieros y sin poder modificar servicios.
"""
from datetime import date

from django.urls import reverse

from api.tests_pagos import BaseFinanzasTests
from core.models import (
    Alumno,
    Curso,
    CursoCursaMaterias,
    Docente,
    DocenteDictaMateria,
    Materia,
    Persona,
    Preceptor,
)


class RolesPersonalTests(BaseFinanzasTests):
    def setUp(self):
        super().setUp()

        # Datos de contacto del alumno y de su tutor, que el docente y el preceptor no deben ver.
        persona = self.alumno.id_persona
        persona.direccion = "Calle Falsa 123"
        persona.telefono = "3624111222"
        persona.email = "hijo@test.invalid"
        persona.save()

        # Un alumno de otro curso, que ni el docente ni el preceptor de la prueba tienen a cargo.
        self.curso_otro = Curso.objects.create(nivel="Primario", anio=2, comision="B", turno="Tarde")
        self.alumno_otro_curso = Alumno.objects.create(
            id_persona=Persona.objects.create(
                dni="50000003", nombre="Otro", apellido="Curso", fecha_nacimiento=date(2014, 1, 1),
            ),
            id_curso=self.curso_otro,
            estado="Activo",
        )

        # Docente que dicta una materia en el curso de la prueba (self.curso).
        self.docente_user = self.usuario("docente_prueba")
        self.docente = Docente.objects.create(
            id_persona=self.persona(self.docente_user, "30000001", "Docente"), titulo="Profesor",
        )
        materia = Materia.objects.create(nombre="Lengua", descripcion="", carga_horaria=3, cantidad_clases=40)
        CursoCursaMaterias.objects.create(id_curso=self.curso, id_materia=materia, horarios="Lunes 8:00")
        DocenteDictaMateria.objects.create(id_docente=self.docente, id_materia=materia)

        # Preceptor asignado al curso de la prueba.
        self.preceptor_user = self.usuario("preceptor_prueba")
        self.preceptor = Preceptor.objects.create(
            id_persona=self.persona(self.preceptor_user, "30000002", "Preceptor"),
            fecha_ingreso=date(2020, 1, 1),
        )
        self.curso.legajo_preceptor = self.preceptor
        self.curso.save()

    def legajos(self, ruta):
        respuesta = self.api.get(ruta)
        self.assertEqual(respuesta.status_code, 200)
        return {a["legajo"] for a in respuesta.json()}

    def test_docente_y_preceptor_solo_ven_alumnos_de_sus_cursos(self):
        esperados = {self.alumno.legajo, self.alumno_ajeno.legajo}
        for usuario in (self.docente_user, self.preceptor_user):
            with self.subTest(usuario=usuario.nombre_usuario):
                self.autenticar(usuario)
                self.assertEqual(self.legajos("/api/alumnos/"), esperados)
                self.assertEqual(self.legajos("/api/servicios/alumnos/"), esperados)

    def test_docente_y_preceptor_no_ven_contacto_ni_tutor(self):
        for usuario in (self.docente_user, self.preceptor_user):
            with self.subTest(usuario=usuario.nombre_usuario):
                self.autenticar(usuario)
                alumno = next(a for a in self.api.get("/api/alumnos/").json() if a["legajo"] == self.alumno.legajo)
                self.assertEqual(alumno["direccion"], "")
                self.assertEqual(alumno["telefono"], "")
                self.assertEqual(alumno["email"], "")
                self.assertIsNone(alumno["tutor"])
                self.assertTrue(alumno["dni"])  # el DNI sí se muestra, como en la web

    def test_administrativo_sigue_viendo_todos_con_datos_completos(self):
        self.autenticar(self.admin_web())
        lista = self.api.get("/api/alumnos/").json()
        self.assertIn(self.alumno_otro_curso.legajo, {a["legajo"] for a in lista})
        propio = next(a for a in lista if a["legajo"] == self.alumno.legajo)
        self.assertEqual(propio["direccion"], "Calle Falsa 123")
        self.assertIsNotNone(propio["tutor"])

    def test_docente_y_preceptor_no_acceden_a_datos_financieros(self):
        for usuario in (self.docente_user, self.preceptor_user):
            with self.subTest(usuario=usuario.nombre_usuario):
                self.autenticar(usuario)
                legajo = self.alumno.legajo
                self.assertEqual(self.api.get(f"/api/deuda/?alumno={legajo}").status_code, 403)
                self.assertEqual(self.api.get(f"/api/cuotas/?alumno={legajo}").status_code, 403)
                self.assertEqual(self.api.get(f"/api/facturas/{self.factura.id}/").status_code, 403)
                self.assertEqual(self.api.get(f"/api/facturas/{self.factura.id}/pdf/").status_code, 403)
                self.assertEqual(self.api.get("/api/facturas/").json(), [])

    def test_docente_y_preceptor_no_modifican_servicios(self):
        url = reverse("api-servicios-comedor")
        for usuario in (self.docente_user, self.preceptor_user):
            with self.subTest(usuario=usuario.nombre_usuario):
                self.autenticar(usuario)
                respuesta = self.api.put(
                    url, {"alumno_id": self.alumno.legajo, "inscripto": True}, format="json",
                )
                self.assertEqual(respuesta.status_code, 403)
        self.alumno.refresh_from_db()
        self.assertFalse(self.alumno.inscripto_comedor)

    def test_docente_y_preceptor_si_pueden_consultar_servicios_de_sus_alumnos(self):
        for usuario in (self.docente_user, self.preceptor_user):
            with self.subTest(usuario=usuario.nombre_usuario):
                self.autenticar(usuario)
                propio = self.api.get(f"/api/servicios/mis-servicios/?alumno={self.alumno.legajo}")
                ajeno = self.api.get(f"/api/servicios/mis-servicios/?alumno={self.alumno_otro_curso.legajo}")
                self.assertEqual(propio.status_code, 200)
                self.assertEqual(ajeno.status_code, 403)

    def test_tutor_si_puede_modificar_servicios_de_su_hijo(self):
        self.autenticar(self.tutor_user)
        respuesta = self.api.put(
            reverse("api-servicios-comedor"),
            {"alumno_id": self.alumno.legajo, "inscripto": True},
            format="json",
        )
        self.assertEqual(respuesta.status_code, 200)
        self.alumno.refresh_from_db()
        self.assertTrue(self.alumno.inscripto_comedor)
