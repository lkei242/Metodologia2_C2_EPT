"""Pruebas de la API de pagos, comprobantes y recuperación de contraseña (Luka)."""
import re
from datetime import date
from decimal import Decimal

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.facturacion import generar_factura
from core.models import (
    Alumno,
    Arancel,
    ComprobantePago,
    Cuota,
    Curso,
    Factura,
    Persona,
    PersonalAdministrativo,
    SolicitudPago,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
)
from core.seguridad import guardar_contrasenia


class BaseFinanzasTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        self.curso = Curso.objects.create(nivel="Primario", anio=1, comision="A", turno="Mañana")
        Arancel.objects.create(nivel="Primario", monto=Decimal("10000.00"))

        self.tutor_user = self.usuario("tutor_luka")
        self.tutor = Tutor.objects.create(id_persona=self.persona(self.tutor_user, "40000001", "Tutor"))
        self.alumno = self.alumno_con_persona("50000001")
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.alumno)

        self.otro_user = self.usuario("otro_tutor")
        self.otro_tutor = Tutor.objects.create(id_persona=self.persona(self.otro_user, "40000002", "Otro"))
        self.alumno_ajeno = self.alumno_con_persona("50000002")
        TutorTutoraAlumno.objects.create(id_tutor=self.otro_tutor, id_alumno=self.alumno_ajeno)

        self.factura, _ = generar_factura(self.alumno, "2026-11", date(2026, 11, 1))

    def usuario(self, nombre):
        return Usuario.objects.create(
            nombre_usuario=nombre,
            contrasenia=guardar_contrasenia("clave-segura-1"),
            correo=f"{nombre}@test.invalid",
        )

    def persona(self, usuario, dni, nombre):
        return Persona.objects.create(
            id_usuario=usuario, dni=dni, nombre=nombre, apellido="Prueba", fecha_nacimiento=date(1980, 1, 1),
        )

    def alumno_con_persona(self, dni):
        persona = Persona.objects.create(dni=dni, nombre="Hijo", apellido="Prueba", fecha_nacimiento=date(2015, 1, 1))
        return Alumno.objects.create(id_persona=persona, id_curso=self.curso, estado="Activo")

    def autenticar(self, usuario):
        token = RefreshToken()
        token["user_id"] = usuario.id
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {token.access_token}")

    def admin_web(self):
        usuario = self.usuario("admin_luka")
        persona = Persona.objects.create(
            id_usuario=usuario, dni="60000001", nombre="Admin", apellido="Web", fecha_nacimiento=date(1980, 1, 1),
        )
        PersonalAdministrativo.objects.create(
            id_persona=persona, sector="Administración", cargo="Administrador", fecha_ingreso=date(2020, 1, 1),
        )
        return usuario


class ConsultasTests(BaseFinanzasTests):
    def test_tutor_solo_ve_sus_hijos(self):
        self.autenticar(self.tutor_user)
        respuesta = self.api.get("/api/alumnos/")
        legajos = [a["legajo"] for a in respuesta.json()]
        self.assertEqual(legajos, [self.alumno.legajo])

    def test_tutor_no_puede_consultar_deuda_de_hijo_ajeno(self):
        self.autenticar(self.tutor_user)
        respuesta = self.api.get(f"/api/deuda/?alumno={self.alumno_ajeno.legajo}")
        self.assertEqual(respuesta.status_code, 403)

    def test_deuda_muestra_total_y_desglose(self):
        self.autenticar(self.tutor_user)
        datos = self.api.get(f"/api/deuda/?alumno={self.alumno.legajo}").json()
        self.assertEqual(datos["total_deuda"], "10000.00")
        self.assertEqual(len(datos["facturas"][0]["items"]), 1)
        self.assertEqual(datos["facturas"][0]["items"][0]["tipo"], "cuota")

    def test_cuotas_filtra_por_estado(self):
        Cuota.objects.create(
            periodo="2026-10", monto=Decimal("10000"), estado="Pagada", fecha_pago=date(2026, 10, 5),
            id_tutor=self.tutor, id_legajo_alumno=self.alumno,
        )
        Cuota.objects.create(
            periodo="2026-11", monto=Decimal("10000"), estado="Pendiente",
            id_tutor=self.tutor, id_legajo_alumno=self.alumno,
        )
        self.autenticar(self.tutor_user)
        pendientes = self.api.get(f"/api/cuotas/?alumno={self.alumno.legajo}&estado=Pendiente").json()
        self.assertEqual([c["periodo"] for c in pendientes], ["2026-11"])

    def test_facturas_filtra_por_fecha(self):
        self.autenticar(self.tutor_user)
        dentro = self.api.get(f"/api/facturas/?desde=2026-11-01&hasta=2026-11-30").json()
        fuera = self.api.get(f"/api/facturas/?desde=2026-12-01").json()
        self.assertEqual(len(dentro), 1)
        self.assertEqual(fuera, [])

    def test_pdf_de_factura(self):
        self.autenticar(self.tutor_user)
        respuesta = self.api.get(f"/api/facturas/{self.factura.pk}/pdf/")
        self.assertEqual(respuesta.status_code, 200)
        self.assertTrue(respuesta.content.startswith(b"%PDF"))


class PagoTests(BaseFinanzasTests):
    def pagar(self, clave, items):
        return self.api.post(
            "/api/pagos/",
            {"factura": self.factura.pk, "items": items},
            format="json",
            HTTP_IDEMPOTENCY_KEY=clave,
        )

    def test_pago_requiere_clave_de_idempotencia(self):
        self.autenticar(self.tutor_user)
        respuesta = self.api.post("/api/pagos/", {"factura": self.factura.pk, "items": [1]}, format="json")
        self.assertEqual(respuesta.status_code, 400)

    def test_total_lo_calcula_el_servidor_y_no_se_duplica(self):
        self.autenticar(self.tutor_user)
        item_ids = list(self.factura.items.values_list("id", flat=True))
        primera = self.pagar("clave-1", item_ids)
        repetida = self.pagar("clave-1", item_ids)
        self.assertEqual(primera.status_code, 201)
        self.assertEqual(primera.json()["total"], "10000.00")
        self.assertEqual(repetida.status_code, 200)
        self.assertEqual(primera.json()["id"], repetida.json()["id"])
        self.assertEqual(SolicitudPago.objects.count(), 1)

    def test_no_permite_dos_solicitudes_pendientes_por_factura(self):
        self.autenticar(self.tutor_user)
        item_ids = list(self.factura.items.values_list("id", flat=True))
        self.pagar("clave-1", item_ids)
        segunda = self.pagar("clave-2", item_ids)
        self.assertEqual(segunda.status_code, 409)

    def test_alumno_no_puede_pagar(self):
        alumno_user = self.usuario("alumno_luka")
        Persona.objects.filter(pk=self.alumno.id_persona_id).update(id_usuario=alumno_user)
        self.autenticar(alumno_user)
        item_ids = list(self.factura.items.values_list("id", flat=True))
        self.assertEqual(self.pagar("clave-3", item_ids).status_code, 403)


class ComprobanteTests(BaseFinanzasTests):
    def subir(self, nombre, contenido, importe="10000"):
        archivo = SimpleUploadedFile(nombre, contenido, content_type="application/octet-stream")
        return self.api.post(
            f"/api/facturas/{self.factura.pk}/comprobantes/",
            {"archivo": archivo, "importe": importe},
            format="multipart",
        )

    def test_rechaza_archivo_que_no_coincide_con_su_extension(self):
        self.autenticar(self.tutor_user)
        respuesta = self.subir("transferencia.pdf", b"esto no es un pdf")
        self.assertEqual(respuesta.status_code, 400)

    def test_rechaza_formato_no_permitido(self):
        self.autenticar(self.tutor_user)
        respuesta = self.subir("transferencia.exe", b"MZ....")
        self.assertEqual(respuesta.status_code, 400)

    def test_guarda_comprobante_con_nombre_aleatorio(self):
        self.autenticar(self.tutor_user)
        respuesta = self.subir("mi transferencia.pdf", b"%PDF-1.4 contenido")
        self.assertEqual(respuesta.status_code, 201)
        comprobante = ComprobantePago.objects.get()
        self.assertNotIn("mi transferencia", comprobante.archivo.name)
        self.assertEqual(comprobante.estado, "Pendiente")

    def test_otro_tutor_no_descarga_el_comprobante(self):
        self.autenticar(self.tutor_user)
        self.subir("transferencia.pdf", b"%PDF-1.4 contenido")
        comprobante = ComprobantePago.objects.get()

        self.autenticar(self.otro_user)
        respuesta = self.api.get(f"/api/comprobantes/{comprobante.pk}/archivo/")
        self.assertEqual(respuesta.status_code, 403)


class SeguridadTests(BaseFinanzasTests):
    def test_login_no_acepta_contrasenia_en_texto_plano(self):
        Usuario.objects.create(nombre_usuario="plano", contrasenia="clave-plana", correo="plano@test.invalid")
        respuesta = self.api.post("/api/login/", {"usuario": "plano", "password": "clave-plana"}, format="json")
        self.assertEqual(respuesta.status_code, 401)

    def test_login_acepta_contrasenia_con_hash(self):
        respuesta = self.api.post("/api/login/", {"usuario": "tutor_luka", "password": "clave-segura-1"}, format="json")
        self.assertEqual(respuesta.status_code, 200)

    def test_recuperacion_no_revela_si_la_cuenta_existe(self):
        existe = self.api.post("/api/recuperar-contrasena/", {"correo": "tutor_luka@test.invalid"}, format="json")
        no_existe = self.api.post("/api/recuperar-contrasena/", {"correo": "nadie@test.invalid"}, format="json")
        self.assertEqual(existe.json()["mensaje"], no_existe.json()["mensaje"])

    def test_token_de_recuperacion_sirve_una_sola_vez(self):
        self.api.post("/api/recuperar-contrasena/", {"correo": "tutor_luka@test.invalid"}, format="json")
        cuerpo = mail.outbox[-1].body
        token = re.search(r"\n\n(\S+)\n\n", cuerpo).group(1)

        primera = self.api.post(
            "/api/recuperar-contrasena/confirmar/", {"token": token, "nueva": "nueva-clave-456"}, format="json",
        )
        segunda = self.api.post(
            "/api/recuperar-contrasena/confirmar/", {"token": token, "nueva": "otra-clave-789"}, format="json",
        )
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(segunda.status_code, 400)

        ingreso = self.api.post("/api/login/", {"usuario": "tutor_luka", "password": "nueva-clave-456"}, format="json")
        self.assertEqual(ingreso.status_code, 200)

    def test_no_se_envia_contrasenia_por_correo(self):
        self.api.post("/api/recuperar-contrasena/", {"correo": "tutor_luka@test.invalid"}, format="json")
        self.assertNotIn("clave-segura-1", mail.outbox[-1].body)


class AprobacionWebTests(BaseFinanzasTests):
    def setUp(self):
        super().setUp()
        self.admin = self.admin_web()
        self.comprobante = ComprobantePago.objects.create(
            factura=self.factura, archivo="comprobantes/2026-11/prueba.pdf", importe=Decimal("10000"),
        )

    def sesion(self, usuario):
        sesion = self.client.session
        sesion["usuario_id"] = usuario.pk
        sesion.save()

    def test_aprobar_cubre_total_y_marca_factura_pagada(self):
        self.sesion(self.admin)
        self.client.post(reverse("aprobar-comprobante", args=[self.comprobante.pk]))
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado, "Pagada")
        self.assertTrue(Cuota.objects.filter(id_legajo_alumno=self.alumno, estado="Pagada").exists())

    def test_aprobar_parcial_deja_factura_parcial(self):
        self.comprobante.importe = Decimal("4000")
        self.comprobante.save()
        self.sesion(self.admin)
        self.client.post(reverse("aprobar-comprobante", args=[self.comprobante.pk]))
        self.factura.refresh_from_db()
        self.assertEqual(self.factura.estado, "Parcial")

    def test_tutor_no_puede_aprobar(self):
        self.sesion(self.tutor_user)
        respuesta = self.client.post(reverse("aprobar-comprobante", args=[self.comprobante.pk]))
        self.assertEqual(respuesta.status_code, 403)
        self.comprobante.refresh_from_db()
        self.assertEqual(self.comprobante.estado, "Pendiente")
