"""Pruebas de las correcciones surgidas de la revisión contra la consigna del TPI."""
import os
from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.messages import get_messages
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    Alumno, Arancel, AuditoriaCambio, Aula, ComprobantePago, Curso, CursoCursaMaterias,
    DisciplinaDeportiva, DocumentacionAlumno, Docente, DocenteCursoMateria, Factura, GrupoDeportivo,
    InscripcionDeportiva, Instalacion, Materia, PagoPendiente, Persona,
    PersonalAdministrativo, Preceptor, RecorridoTransporte, Reserva,
    SolicitudInscripcion, Tutor, TutorTutoraAlumno, Usuario, ValorComedor,
)
from .reporting_views import _formatear_horarios


class CorreccionesBase(TestCase):
    def setUp(self):
        self.admin_user = Usuario.objects.create(nombre_usuario="admin_correcciones", contrasenia="x")
        persona = Persona.objects.create(
            id_usuario=self.admin_user, dni="10000101", nombre="Admin", apellido="Prueba",
            fecha_nacimiento=date(1980, 1, 1),
        )
        PersonalAdministrativo.objects.create(
            id_persona=persona, sector="Sistemas", cargo="Administrador", fecha_ingreso=date(2020, 1, 1),
        )
        self.curso = Curso.objects.create(nivel="Primario", anio=1, comision="A", turno="Mañana")
        self.entrar(self.admin_user)

    def entrar(self, usuario):
        sesion = self.client.session
        sesion["usuario_id"] = usuario.pk
        sesion.save()

    def mensajes(self, respuesta):
        return list(get_messages(respuesta.wsgi_request))

    def crear_alumno_con_usuario(self, dni="50000111"):
        usuario = Usuario.objects.create(nombre_usuario=f"alumno{dni}", contrasenia="x")
        persona = Persona.objects.create(
            id_usuario=usuario, dni=dni, nombre="Lia", apellido="Alumna", fecha_nacimiento=date(2014, 1, 1),
        )
        alumno = Alumno.objects.create(id_persona=persona, id_curso=self.curso, estado="Activo")
        return usuario, alumno

    def crear_tutor(self, usuario, dni):
        user = Usuario.objects.create(nombre_usuario=usuario, contrasenia="x")
        persona = Persona.objects.create(
            id_usuario=user, dni=dni, nombre="Tutor", apellido=usuario, fecha_nacimiento=date(1980, 1, 1),
        )
        return user, Tutor.objects.create(id_persona=persona)

    def crear_grupo(self, nombre, dia="Lunes", inicio="08:00", fin="09:00"):
        instalacion, _ = Instalacion.objects.get_or_create(
            nombre="Gimnasio", defaults={"capacidad": 30, "estado": "Activo"},
        )
        persona, _ = Persona.objects.get_or_create(
            dni="30000888", defaults={"nombre": "Profe", "apellido": "Deporte", "fecha_nacimiento": date(1980, 1, 1)},
        )
        docente, _ = Docente.objects.get_or_create(id_persona=persona, defaults={"titulo": "Profesor"})
        disciplina = DisciplinaDeportiva.objects.create(nombre=nombre, horarios="", id_instalacion=instalacion)
        return GrupoDeportivo.objects.create(
            disciplina=disciplina, nivel="Primario", dia_semana=dia,
            hora_inicio=inicio, hora_fin=fin, profesor_responsable=docente,
        )


class ContactoTests(CorreccionesBase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_la_consulta_se_envia_por_correo_de_django_si_no_hay_resend(self):
        with mock.patch.dict(os.environ, {"RESEND_API_KEY": ""}):
            respuesta = self.client.post(reverse("enviar-consulta"), {
                "nombre": "Ana Gomez", "email": "ana@test.com", "mensaje": "Hola, quiero consultar.",
                "origen": "contacto",
            })
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Hola, quiero consultar.", mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].reply_to, ["ana@test.com"])

    def test_si_falla_el_envio_se_informa_sin_error_500(self):
        with mock.patch("core.views._enviar_consulta_por_correo", side_effect=RuntimeError("sin red")):
            with self.assertLogs("core.views", level="ERROR"):
                respuesta = self.client.post(reverse("enviar-consulta"), {
                    "nombre": "Ana Gomez", "email": "ana@test.com", "mensaje": "Hola", "origen": "contacto",
                })
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(any("No pudimos enviar" in str(m) for m in self.mensajes(respuesta)))

    def test_entrar_por_get_no_da_error(self):
        self.assertEqual(self.client.get(reverse("enviar-consulta")).status_code, 302)


class AprobarInscripcionTests(CorreccionesBase):
    def crear_solicitud_inicial(self):
        nacimiento = date.today() - timedelta(days=int(365.25 * 4) + 30)  # 4 años
        return SolicitudInscripcion.objects.create(
            nombre_alumno="Mia", apellido_alumno="Chica", dni_alumno="60000001", fecha_nacimiento=nacimiento,
            nivel="inicial", turno="mañana", nombre_tutor="Tu", apellido_tutor="Tor", dni_tutor="20000001",
            telefono="3624000000", email="tutor@test.com", direccion="Calle 1",
            fecha_solicitud=timezone.now(), parentesco="Madre",
        )

    def test_se_aprueba_una_solicitud_de_nivel_inicial(self):
        sala = Curso.objects.create(nivel="Inicial", anio=2, comision="A", turno="Mañana")
        solicitud = self.crear_solicitud_inicial()
        self.client.post(reverse("aprobar-inscripcion", args=[solicitud.pk]))
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "Aprobada")
        self.assertEqual(Alumno.objects.get(id_persona__dni="60000001").id_curso, sala)

    def test_sin_curso_compatible_se_explica_el_motivo_en_el_panel(self):
        solicitud = self.crear_solicitud_inicial()
        respuesta = self.client.post(reverse("aprobar-inscripcion", args=[solicitud.pk]), follow=True)
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, "Pendiente")
        self.assertContains(respuesta, "No hay un curso de nivel Inicial")


class DeportesDelAlumnoTests(CorreccionesBase):
    def test_el_alumno_se_inscribe_a_grupos_con_limite_y_auditoria(self):
        usuario, alumno = self.crear_alumno_con_usuario()
        natacion = self.crear_grupo("Natación")
        futbol = self.crear_grupo("Fútbol", inicio="09:00", fin="10:00")
        voley = self.crear_grupo("Vóley", dia="Martes")
        self.entrar(usuario)
        url = reverse("dashboard-alumno")

        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": natacion.pk})
            self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": futbol.pk})
        self.assertEqual(InscripcionDeportiva.objects.filter(alumno=alumno, estado="Activa").count(), 2)
        self.assertEqual(AuditoriaCambio.objects.filter(entidad="InscripcionDeportiva", accion="inscribir").count(), 2)
        alumno.refresh_from_db()
        self.assertIsNone(alumno.id_disciplina_id, "No debe usar el campo heredado de una sola disciplina.")

        respuesta = self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": voley.pk}, follow=True)
        self.assertContains(respuesta, "no puede tener más de dos")
        self.assertEqual(InscripcionDeportiva.objects.filter(alumno=alumno, estado="Activa").count(), 2)

    def test_se_rechaza_un_horario_superpuesto(self):
        usuario, alumno = self.crear_alumno_con_usuario()
        natacion = self.crear_grupo("Natación")
        hockey = self.crear_grupo("Hockey", inicio="08:30", fin="09:30")
        self.entrar(usuario)
        url = reverse("dashboard-alumno")
        self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": natacion.pk})
        respuesta = self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": hockey.pk}, follow=True)
        self.assertContains(respuesta, "se superpone")
        self.assertEqual(InscripcionDeportiva.objects.filter(alumno=alumno, estado="Activa").count(), 1)

    def test_el_alumno_puede_finalizar_su_inscripcion_y_elegir_otro_deporte(self):
        usuario, alumno = self.crear_alumno_con_usuario()
        grupos = [
            self.crear_grupo("Natación"),
            self.crear_grupo("Fútbol", inicio="09:00", fin="10:00"),
            self.crear_grupo("Vóley", dia="Martes"),
        ]
        self.entrar(usuario)
        url = reverse("dashboard-alumno")
        for grupo in grupos[:2]:
            self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": grupo.pk})
        primera = InscripcionDeportiva.objects.get(alumno=alumno, grupo=grupos[0])
        self.client.post(url, {"accion": "finalizar_deporte", "id_inscripcion": primera.pk})
        primera.refresh_from_db()
        self.assertEqual(primera.estado, "Finalizada")
        self.client.post(url, {"accion": "inscribir_deporte", "id_grupo": grupos[2].pk})
        self.assertEqual(InscripcionDeportiva.objects.filter(alumno=alumno, estado="Activa").count(), 2)

    def test_un_alumno_no_puede_finalizar_la_inscripcion_de_otro(self):
        usuario, _ = self.crear_alumno_con_usuario()
        _, otro = self.crear_alumno_con_usuario(dni="50000222")
        grupo = self.crear_grupo("Natación")
        ajena = InscripcionDeportiva.objects.create(alumno=otro, grupo=grupo, estado="Activa")
        self.entrar(usuario)
        self.client.post(reverse("dashboard-alumno"), {"accion": "finalizar_deporte", "id_inscripcion": ajena.pk})
        ajena.refresh_from_db()
        self.assertEqual(ajena.estado, "Activa")

    def test_el_panel_lista_los_grupos_disponibles(self):
        usuario, _ = self.crear_alumno_con_usuario()
        self.crear_grupo("Natación")
        self.entrar(usuario)
        respuesta = self.client.get(reverse("dashboard-alumno"))
        self.assertContains(respuesta, "Natación")
        self.assertContains(respuesta, "Lunes 08:00-09:00")


class ValoresTests(CorreccionesBase):
    def setUp(self):
        super().setUp()
        self.arancel = Arancel.objects.create(nivel="Primario", monto=Decimal("25000.00"))
        self.grupo = self.crear_grupo("Judo")
        self.disciplina = self.grupo.disciplina
        self.recorrido = RecorridoTransporte.objects.create(nombre="Recorrido Norte", descripcion="x", activo=True)

    def test_los_campos_se_precargan_con_punto_decimal(self):
        self.disciplina.valor = Decimal("8000.50")
        self.disciplina.save(update_fields=["valor"])
        respuesta = self.client.get(reverse("gestion-valores"))
        self.assertContains(respuesta, 'value="25000.00"')
        self.assertContains(respuesta, 'value="8000.50"')

    def test_se_fijan_los_valores_que_usa_la_facturacion(self):
        respuesta = self.client.post(reverse("gestion-valores"), {
            f"monto_{self.arancel.pk}": "26000,50",
            f"disc_{self.disciplina.pk}": "8000",
            f"rec_{self.recorrido.pk}": "15000.5",
            "comedor": "12000",
        })
        self.assertRedirects(respuesta, reverse("gestion-valores"))
        self.arancel.refresh_from_db()
        self.disciplina.refresh_from_db()
        self.recorrido.refresh_from_db()
        self.assertEqual(self.arancel.monto, Decimal("26000.50"))
        self.assertEqual(self.disciplina.valor, Decimal("8000.00"))
        self.assertEqual(self.recorrido.valor, Decimal("15000.50"))
        self.assertEqual(ValorComedor.objects.get().monto, Decimal("12000.00"))

    def test_un_valor_invalido_no_modifica_nada(self):
        respuesta = self.client.post(reverse("gestion-valores"), {
            f"monto_{self.arancel.pk}": "30000", "comedor": "abc", f"rec_{self.recorrido.pk}": "-5",
        })
        self.arancel.refresh_from_db()
        self.assertEqual(self.arancel.monto, Decimal("25000.00"))
        self.assertFalse(ValorComedor.objects.exists())
        textos = [str(m) for m in self.mensajes(respuesta)]
        self.assertTrue(any("Comedor" in t for t in textos))
        self.assertTrue(any("Recorrido Norte" in t for t in textos))

    def test_la_cuota_por_nivel_sigue_siendo_la_fuente_de_la_facturacion(self):
        from .facturacion import calcular_items
        self.client.post(reverse("gestion-valores"), {f"monto_{self.arancel.pk}": "31000"})
        _, alumno = self.crear_alumno_con_usuario()
        items = calcular_items(alumno)
        self.assertEqual(items[0][2], Decimal("31000.00"))


class ReporteDocenteTests(CorreccionesBase):
    def test_formatear_horarios(self):
        self.assertEqual(
            _formatear_horarios('{"Miércoles": "08:00-09:00", "Lunes": "10:00-11:00"}'),
            "Lunes 10:00-11:00; Miércoles 08:00-09:00",
        )
        self.assertEqual(_formatear_horarios("Lunes 8:00"), "Lunes 8:00")
        self.assertEqual(_formatear_horarios(None), "Sin horario cargado")

    def test_r02_muestra_el_horario_legible(self):
        persona = Persona.objects.create(dni="30000777", nombre="Sara", apellido="Gomez", fecha_nacimiento=date(1980, 1, 1))
        docente = Docente.objects.create(id_persona=persona, titulo="Profesora", especialidad="Filosofía")
        materia = Materia.objects.create(nombre="Filosofía", descripcion="", carga_horaria=2, cantidad_clases=30)
        CursoCursaMaterias.objects.create(id_curso=self.curso, id_materia=materia, horarios='{"Martes": "11:00-12:20"}')
        DocenteCursoMateria.objects.create(docente=docente, curso=self.curso, materia=materia)
        respuesta = self.client.get(reverse("reportes"), {"reporte": "R-02"})
        self.assertContains(respuesta, "Martes 11:00-12:20")
        self.assertNotContains(respuesta, "&quot;Martes&quot;")


class ReservasTests(CorreccionesBase):
    def setUp(self):
        super().setUp()
        self.cancha = Instalacion.objects.create(nombre="Cancha de Fútbol", capacidad=50, estado="Disponible")
        self.gimnasio = Instalacion.objects.create(nombre="Gimnasio", capacidad=80, estado="Disponible")
        Persona.objects.create(dni="40000555", nombre="Ana", apellido="Lopez", fecha_nacimiento=date(1990, 1, 1))
        self.fecha = (date.today() + timedelta(days=5)).isoformat()

    def reservar(self, horario, espacio=None):
        return self.client.post(reverse("crear-reserva"), {
            "espacio": (espacio or self.cancha).pk, "fecha": self.fecha,
            "horario": horario, "responsable": "Ana Lopez",
        }, follow=True)

    def cantidad(self, espacio=None):
        return Reserva.objects.filter(id_instalacion=espacio or self.cancha).count()

    def test_se_registra_una_reserva_valida(self):
        respuesta = self.reservar("16:00 - 17:00")
        self.assertContains(respuesta, "Reserva registrada correctamente")
        self.assertEqual(self.cantidad(), 1)

    def test_se_rechazan_reservas_que_se_superponen(self):
        self.reservar("16:00 - 17:00")
        for horario in ("16:30 - 17:30", "15:30 - 16:30", "16:15 - 16:45", "15:00 - 18:00", "16:00 - 17:00"):
            respuesta = self.reservar(horario)
            self.assertContains(respuesta, "se superpone", msg_prefix=horario)
        self.assertEqual(self.cantidad(), 1)

    def test_una_reserva_contigua_o_en_otro_espacio_no_es_conflicto(self):
        self.reservar("16:00 - 17:00")
        self.reservar("17:00 - 18:00")
        self.reservar("15:00 - 16:00")
        self.reservar("16:00 - 17:00", espacio=self.gimnasio)
        self.assertEqual(self.cantidad(), 3)
        self.assertEqual(self.cantidad(self.gimnasio), 1)

    def test_la_hora_de_fin_debe_ser_posterior_a_la_de_inicio(self):
        respuesta = self.reservar("17:00 - 16:00")
        self.assertContains(respuesta, "posterior a la hora de inicio")
        self.assertEqual(self.cantidad(), 0)


class HistorialDePagosDelTutorTests(CorreccionesBase):
    def setUp(self):
        super().setUp()
        self.tutor_usuario, self.tutor = self.crear_tutor("tutor_hist", "20000111")
        _, self.alumno = self.crear_alumno_con_usuario(dni="50000333")
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.alumno, tipo_parentesco="Padre")
        self.factura = Factura.objects.create(
            alumno=self.alumno, tutor=self.tutor, periodo="2026-11",
            emision=date(2026, 11, 1), vencimiento=date(2026, 12, 10), total=Decimal("69000.00"),
        )
        self.entrar(self.tutor_usuario)

    def comprobante(self, estado, importe="69000.00", factura=None):
        return ComprobantePago.objects.create(
            factura=factura or self.factura, archivo="comprobantes/prueba.pdf",
            importe=Decimal(importe), estado=estado,
        )

    def fila(self):
        filas = self.client.get(reverse("dashboard-padres")).context["facturas_historial"]
        self.assertEqual(len(filas), 1)
        return filas[0]

    def test_una_factura_sin_pagos_figura_pendiente_de_pago(self):
        fila = self.fila()
        self.assertEqual(fila["estado"], "Pendiente de pago")
        self.assertEqual(fila["saldo"], Decimal("69000.00"))
        self.assertEqual(fila["comprobantes"], [])

    def test_un_comprobante_recien_cargado_figura_en_revision(self):
        self.comprobante("Pendiente")
        fila = self.fila()
        self.assertEqual(fila["estado"], "Comprobante en revisión")
        self.assertEqual(fila["pagado"], Decimal("0"))
        respuesta = self.client.get(reverse("dashboard-padres"))
        self.assertContains(respuesta, "En revisión")

    def test_un_comprobante_rechazado_se_informa(self):
        self.comprobante("Rechazado")
        self.assertIn("rechazado", self.fila()["estado"])

    def test_un_pago_parcial_muestra_lo_acreditado_y_el_saldo(self):
        self.comprobante("Aprobado", importe="30000.00")
        self.factura.estado = "Parcial"
        self.factura.save(update_fields=["estado"])
        fila = self.fila()
        self.assertEqual(fila["estado"], "Pago parcial")
        self.assertEqual(fila["pagado"], Decimal("30000.00"))
        self.assertEqual(fila["saldo"], Decimal("39000.00"))

    def test_una_factura_pagada_se_muestra_pagada_y_sin_saldo(self):
        self.comprobante("Aprobado")
        self.factura.estado = "Pagada"
        self.factura.save(update_fields=["estado"])
        fila = self.fila()
        self.assertEqual(fila["estado"], "Pagada")
        self.assertEqual(fila["saldo"], Decimal("0"))

    def test_el_tutor_no_ve_las_facturas_de_otra_familia(self):
        _, otro_tutor = self.crear_tutor("tutor_ajeno", "20000222")
        _, otro_alumno = self.crear_alumno_con_usuario(dni="50000444")
        TutorTutoraAlumno.objects.create(id_tutor=otro_tutor, id_alumno=otro_alumno, tipo_parentesco="Madre")
        ajena = Factura.objects.create(
            alumno=otro_alumno, tutor=otro_tutor, periodo="2026-11",
            emision=date(2026, 11, 1), vencimiento=date(2026, 12, 10), total=Decimal("1000.00"),
        )
        self.comprobante("Pendiente", importe="1000.00", factura=ajena)
        fila = self.fila()
        self.assertEqual(fila["factura"], self.factura)
        self.assertEqual(fila["comprobantes"], [])

    def test_un_pago_del_flujo_anterior_pendiente_tambien_se_muestra(self):
        PagoPendiente.objects.create(
            id_tutor=self.tutor, legajo_alumno=self.alumno, mes="Abril",
            importe=Decimal("32000.00"), estado="Pendiente", fecha_solicitud=timezone.now(),
        )
        respuesta = self.client.get(reverse("dashboard-padres"))
        self.assertEqual(len(respuesta.context["pagos_en_revision"]), 1)
        self.assertContains(respuesta, "Pagos enviados pendientes de aprobación")


class DocumentacionDelTutorTests(CorreccionesBase):
    def setUp(self):
        super().setUp()
        self.tutor_usuario, self.tutor = self.crear_tutor("tutor_docs", "20000333")
        _, self.lucas = self.crear_alumno_con_usuario(dni="50000501")
        _, self.valentina = self.crear_alumno_con_usuario(dni="50000502")
        self.lucas.id_persona.nombre, self.valentina.id_persona.nombre = "Lucas", "Valentina"
        self.lucas.id_persona.save(update_fields=["nombre"])
        self.valentina.id_persona.save(update_fields=["nombre"])
        for hijo in (self.lucas, self.valentina):
            TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=hijo, tipo_parentesco="Padre")
        self.entrar(self.tutor_usuario)

    def documentacion(self, alumno, estado, observaciones=None):
        return DocumentacionAlumno.objects.create(
            legajo_alumno=alumno, dni_frente="documentacion/a.jpg", dni_dorso="documentacion/b.jpg",
            partida_nacimiento="documentacion/c.jpg", certificado_salud="documentacion/d.jpg",
            fecha_envio=timezone.now(), estado=estado, observaciones=observaciones,
        )

    def contexto(self):
        return self.client.get(reverse("dashboard-padres")).context

    def estados(self):
        return {h["persona"].nombre: h["doc"]["clave"] for h in self.contexto()["hijos"]}

    def archivos(self):
        return {
            nombre: SimpleUploadedFile(f"{nombre}.jpg", b"contenido", content_type="image/jpeg")
            for nombre in ("dni_frente", "dni_dorso", "partida", "salud")
        }

    def enviar(self, alumno, **extra_archivos):
        archivos = self.archivos()
        archivos.update(extra_archivos)
        with mock.patch("core.views.FileSystemStorage") as almacenamiento:
            almacenamiento.return_value.save.side_effect = lambda nombre, archivo: nombre
            return self.client.post(
                reverse("enviar_documentacion"), {"alumno": alumno.pk, **archivos}, follow=True,
            )

    def test_cada_hijo_muestra_su_estado_y_quien_no_envio_figura_como_falta(self):
        self.documentacion(self.lucas, "Pendiente")
        self.assertEqual(self.estados(), {"Lucas": "revision", "Valentina": "falta"})
        respuesta = self.client.get(reverse("dashboard-padres"))
        self.assertContains(respuesta, "Falta presentar")
        self.assertContains(respuesta, "En revisión")
        resumen = respuesta.context["resumen_documentacion"]
        self.assertEqual((resumen["revision"], resumen["falta"], resumen["total"]), (1, 1, 2))

    def test_el_desplegable_solo_ofrece_a_quienes_pueden_enviar(self):
        self.documentacion(self.lucas, "Pendiente")
        pendientes = [h["persona"].nombre for h in self.contexto()["hijos_que_pueden_enviar"]]
        self.assertEqual(pendientes, ["Valentina"])

    def test_aprobada_y_en_revision_no_se_vuelven_a_ofrecer_pero_rechazada_si(self):
        self.documentacion(self.lucas, "Aprobada")
        self.documentacion(self.valentina, "Rechazada", observaciones="La foto del DNI está borrosa")
        self.assertEqual(self.estados(), {"Lucas": "aprobada", "Valentina": "rechazada"})
        pendientes = [h["persona"].nombre for h in self.contexto()["hijos_que_pueden_enviar"]]
        self.assertEqual(pendientes, ["Valentina"])
        self.assertContains(self.client.get(reverse("dashboard-padres")), "La foto del DNI está borrosa")

    def test_con_todo_presentado_se_oculta_el_formulario(self):
        self.documentacion(self.lucas, "Aprobada")
        self.documentacion(self.valentina, "Pendiente")
        respuesta = self.client.get(reverse("dashboard-padres"))
        self.assertNotContains(respuesta, 'name="dni_frente"')
        self.assertContains(respuesta, "No hay documentación pendiente de enviar")

    def test_al_enviar_el_hijo_pasa_a_en_revision_y_sale_de_la_lista(self):
        respuesta = self.enviar(self.valentina)
        self.assertContains(respuesta, "quedó en revisión")
        self.assertEqual(self.estados()["Valentina"], "revision")
        pendientes = [h["persona"].nombre for h in self.contexto()["hijos_que_pueden_enviar"]]
        self.assertEqual(pendientes, ["Lucas"])

    def test_no_se_puede_reenviar_documentacion_aprobada(self):
        self.documentacion(self.lucas, "Aprobada")
        respuesta = self.enviar(self.lucas)
        self.assertContains(respuesta, "ya fue aprobada")
        self.assertEqual(DocumentacionAlumno.objects.filter(legajo_alumno=self.lucas).count(), 1)

    def test_no_se_puede_reenviar_documentacion_en_revision(self):
        self.documentacion(self.lucas, "Pendiente")
        respuesta = self.enviar(self.lucas)
        self.assertContains(respuesta, "está en revisión")
        self.assertEqual(DocumentacionAlumno.objects.filter(legajo_alumno=self.lucas).count(), 1)

    def test_un_reenvio_invalido_conserva_el_rechazo_y_uno_valido_lo_reemplaza(self):
        self.documentacion(self.lucas, "Rechazada", observaciones="Falta el dorso")
        invalido = SimpleUploadedFile("salud.pdf", b"x", content_type="application/pdf")
        self.enviar(self.lucas, salud=invalido)
        documento = DocumentacionAlumno.objects.get(legajo_alumno=self.lucas)
        self.assertEqual(documento.estado, "Rechazada")
        self.assertEqual(documento.observaciones, "Falta el dorso")

        self.enviar(self.lucas)
        documento = DocumentacionAlumno.objects.get(legajo_alumno=self.lucas)
        self.assertEqual(documento.estado, "Pendiente")

    def test_un_tutor_no_puede_enviar_documentacion_de_hijos_ajenos(self):
        _, ajeno = self.crear_alumno_con_usuario(dni="50000999")
        respuesta = self.enviar(ajeno)
        self.assertEqual(respuesta.status_code, 403)
        self.assertFalse(DocumentacionAlumno.objects.filter(legajo_alumno=ajeno).exists())


class ConsultaDeHijosDelTutorTests(CorreccionesBase):
    def setUp(self):
        super().setUp()
        self.tutor_usuario, self.tutor = self.crear_tutor("tutor_consulta", "20000444")
        _, self.hijo = self.crear_alumno_con_usuario(dni="50000601")
        TutorTutoraAlumno.objects.create(id_tutor=self.tutor, id_alumno=self.hijo, tipo_parentesco="Padre")
        _, self.ajeno = self.crear_alumno_con_usuario(dni="50000602")
        self.entrar(self.tutor_usuario)

    def consultar(self, **filtros):
        return self.client.get(reverse("reportes"), {"reporte": "R-01", **filtros})

    def test_ver_reporte_sin_elegir_hijo_muestra_el_aviso_y_no_falla(self):
        for alumno in ("", "   ", "abc", "1;2", "-1"):
            respuesta = self.consultar(alumno=alumno)
            self.assertEqual(respuesta.status_code, 200, f"alumno={alumno!r}")
            self.assertContains(respuesta, "Seleccioná a tu hijo/a")
            self.assertEqual(respuesta.context["rows"], [])

    def test_sin_el_parametro_tambien_muestra_el_aviso(self):
        respuesta = self.client.get(reverse("reportes"), {"reporte": "R-01"})
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Seleccioná a tu hijo/a")

    def test_con_un_hijo_propio_muestra_su_reporte(self):
        respuesta = self.consultar(alumno=self.hijo.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(len(respuesta.context["rows"]), 1)
        self.assertNotContains(respuesta, "Seleccioná a tu hijo/a")

    def test_con_el_hijo_de_otra_familia_no_muestra_datos(self):
        respuesta = self.consultar(alumno=self.ajeno.pk)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["rows"], [])
        self.assertContains(respuesta, "Seleccioná a tu hijo/a")


class RepresentacionDeModelosTests(TestCase):
    def test_los_modelos_se_muestran_con_un_nombre_legible(self):
        persona = Persona.objects.create(dni="30000555", nombre="Carlos", apellido="Lopez", fecha_nacimiento=date(1980, 1, 1))
        preceptor = Preceptor.objects.create(id_persona=persona, turno="Tarde", fecha_ingreso=date(2020, 1, 1))
        docente = Docente.objects.create(id_persona=persona, titulo="Profesor", especialidad="Matemática")
        aula = Aula.objects.create(nombre="Aula Magna", numero=7, capacidad=30, estado="Activa")
        curso = Curso.objects.create(nivel="Primario", anio=5, comision="B", turno="Tarde")
        for objeto in (preceptor, docente, aula, curso):
            self.assertNotIn("object (", str(objeto))
        self.assertEqual(str(curso), "Primario 5° B - Tarde")
        self.assertEqual(str(docente), "Lopez, Carlos (Matemática)")
        self.assertEqual(str(aula), "Aula Magna (aula 7)")
        self.assertEqual(str(preceptor), "Lopez, Carlos (Tarde)")
