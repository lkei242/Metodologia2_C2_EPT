from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.core.exceptions import ValidationError

from .models import (
    Alumno, AuditoriaCambio, Curso, CursoCursaMaterias, DisciplinaDeportiva,
    Directivo, Docente, DocenteCursoMateria, GrupoDeportivo, Inscripcion,
    InscripcionDeportiva, InscripcionTransporte, Materia, Persona,
    PersonalAdministrativo, Preceptor, RecorridoTransporte, Tutor, TutorTutoraAlumno, Usuario,
)
from .domain_services import ReglaNegocioError, inscribir_en_deporte


class GestionSprint1Tests(TestCase):
    def setUp(self):
        self.admin_user = Usuario.objects.create(nombre_usuario="admin_test", contrasenia="test", correo="admin@test.invalid")
        self.admin_person = Persona.objects.create(
            id_usuario=self.admin_user, dni="10000001", nombre="Admin", apellido="Test",
            fecha_nacimiento=date(1980, 1, 1),
        )
        PersonalAdministrativo.objects.create(id_persona=self.admin_person, sector="Sistemas", cargo="Administrador", fecha_ingreso=date(2020, 1, 1))
        self.course_a = Curso.objects.create(nivel="Primario", anio=1, comision="A", turno="Mañana")
        self.course_b = Curso.objects.create(nivel="Primario", anio=1, comision="B", turno="Mañana")
        self.client.force_login if False else None
        session = self.client.session
        session["usuario_id"] = self.admin_user.pk
        session.save()

    def create_student(self, dni="20000001", course=None):
        person = Persona.objects.create(
            dni=dni, nombre="Ana", apellido="Prueba", fecha_nacimiento=date(2015, 5, 4),
        )
        return Alumno.objects.create(id_persona=person, id_curso=course or self.course_a, estado="Activo")

    def create_group(self, student_name, day="Lunes", starts="08:00", ends="09:00"):
        facility = getattr(self, "facility", None)
        if facility is None:
            from .models import Instalacion
            facility = Instalacion.objects.create(nombre="Gimnasio", capacidad=30, estado="Activo")
            self.facility = facility
        if not hasattr(self, "sport_teacher"):
            person = Persona.objects.create(dni="30000999", nombre="Profe", apellido="Deporte", fecha_nacimiento=date(1980, 1, 1))
            self.sport_teacher = Docente.objects.create(id_persona=person, titulo="Profesor")
        sport = DisciplinaDeportiva.objects.create(nombre=student_name, horarios="", id_instalacion=self.facility)
        return GrupoDeportivo.objects.create(disciplina=sport, nivel="Primario", dia_semana=day, hora_inicio=starts, hora_fin=ends, profesor_responsable=self.sport_teacher)

    def test_hu01_creates_student_and_active_enrollment(self):
        response = self.client.post(reverse("gestion-alumno-nuevo"), {
            "dni": "20000001", "nombre": "Ana", "apellido": "Prueba",
            "fecha_nacimiento": "2015-05-04", "direccion": "Calle 1",
            "telefono": "11223344", "email": "ana@test.invalid",
            "curso": self.course_a.pk, "estado": "Activo",
        })
        self.assertRedirects(response, reverse("gestion-inicio"))
        student = Alumno.objects.get(id_persona__dni="20000001")
        self.assertTrue(student.legajo)
        self.assertEqual(student.id_curso_id, self.course_a.pk)
        self.assertEqual(Inscripcion.objects.filter(legajo_alumno=student, estado="Activa").count(), 1)

    def test_hu01_rejects_duplicate_dni(self):
        self.create_student()
        response = self.client.post(reverse("gestion-alumno-nuevo"), {
            "dni": "20000001", "nombre": "Otra", "apellido": "Persona",
            "fecha_nacimiento": "2015-05-04", "curso": self.course_a.pk,
            "estado": "Activo",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ya existe una persona con ese DNI")
        self.assertEqual(Persona.objects.filter(dni="20000001").count(), 1)

    def test_hu02_creates_teacher_and_course_subject_assignment(self):
        subject = Materia.objects.create(nombre="Ciencias", descripcion="", carga_horaria=3, cantidad_clases=40)
        CursoCursaMaterias.objects.create(id_curso=self.course_a, id_materia=subject, horarios="Lunes 8:00")
        response = self.client.post(reverse("gestion-docente-nuevo"), {
            "dni": "30000001", "nombre": "Luis", "apellido": "Docente",
            "fecha_nacimiento": "1985-03-02", "titulo": "Profesor",
            "especialidad": "Ciencias", "estado": "Activo",
        })
        self.assertRedirects(response, reverse("gestion-inicio"))
        teacher = Docente.objects.get(id_persona__dni="30000001")
        self.assertEqual(teacher.estado, "Activo")
        response = self.client.post(reverse("gestion-academica"), {
            "action": "asignacion", "asignacion-docente": teacher.pk,
            "asignacion-curso": self.course_a.pk, "asignacion-materia": subject.pk,
        })
        self.assertRedirects(response, reverse("gestion-academica"))
        self.assertTrue(DocenteCursoMateria.objects.filter(docente=teacher, curso=self.course_a, materia=subject).exists())

    def test_hu02_assignment_requires_subject_in_course(self):
        teacher_person = Persona.objects.create(dni="30000002", nombre="Luis", apellido="Docente", fecha_nacimiento=date(1985, 3, 2))
        teacher = Docente.objects.create(id_persona=teacher_person, titulo="Profesor", especialidad="Ciencias")
        subject = Materia.objects.create(nombre="Historia", descripcion="", carga_horaria=2, cantidad_clases=30)
        response = self.client.post(reverse("gestion-academica"), {
            "action": "asignacion", "asignacion-docente": teacher.pk,
            "asignacion-curso": self.course_a.pk, "asignacion-materia": subject.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Primero asocie la materia al curso")
        self.assertEqual(DocenteCursoMateria.objects.count(), 0)

    def test_hu03_creates_course_subject_relation(self):
        response = self.client.post(reverse("gestion-academica"), {
            "action": "curso", "curso-nivel": "Secundario", "curso-anio": 2,
            "curso-comision": "C", "curso-turno": "Tarde", "curso-cupo_maximo": "25",
            "curso-legajo_preceptor": "", "curso-id_aula": "",
        })
        self.assertRedirects(response, reverse("gestion-academica"))
        course = Curso.objects.get(nivel="Secundario", comision="C")
        subject = Materia.objects.create(nombre="Lengua", descripcion="", carga_horaria=4, cantidad_clases=40)
        response = self.client.post(reverse("gestion-academica"), {
            "action": "relacion", "relacion-id_curso": course.pk,
            "relacion-id_materia": subject.pk, "relacion-horarios": "Martes 9:00",
        })
        self.assertRedirects(response, reverse("gestion-academica"))
        self.assertTrue(CursoCursaMaterias.objects.filter(id_curso=course, id_materia=subject, horarios="Martes 9:00").exists())

    def test_hu05_changes_course_and_preserves_enrollment_history(self):
        student = self.create_student()
        old = Inscripcion.objects.create(legajo_alumno=student, id_curso=self.course_a, estado="Activa", fecha_inscripcion=date.today())
        response = self.client.post(reverse("gestion-inscripcion"), {
            "legajo_alumno": student.pk, "id_curso": self.course_b.pk, "cambiar_curso": "on",
        })
        self.assertRedirects(response, reverse("gestion-inicio"))
        old.refresh_from_db()
        student.refresh_from_db()
        self.assertEqual(old.estado, "Finalizada")
        self.assertEqual(student.id_curso_id, self.course_b.pk)
        self.assertEqual(Inscripcion.objects.filter(legajo_alumno=student, estado="Activa").count(), 1)

    def test_hu05_rejects_duplicate_active_enrollment(self):
        student = self.create_student()
        Inscripcion.objects.create(legajo_alumno=student, id_curso=self.course_a, estado="Activa", fecha_inscripcion=date.today())
        response = self.client.post(reverse("gestion-inscripcion"), {
            "legajo_alumno": student.pk, "id_curso": self.course_a.pk,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ya está inscripto activamente")
        self.assertEqual(Inscripcion.objects.filter(legajo_alumno=student, estado="Activa").count(), 1)

    def test_database_constraint_allows_only_one_active_enrollment(self):
        student = self.create_student()
        Inscripcion.objects.create(legajo_alumno=student, id_curso=self.course_a, estado="Activa", fecha_inscripcion=date.today())
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Inscripcion.objects.create(legajo_alumno=student, id_curso=self.course_b, estado="Activa", fecha_inscripcion=date.today())

    def test_hu08_anonymous_user_redirects_and_non_admin_is_forbidden(self):
        self.client.logout()
        response = self.client.get(reverse("gestion-inicio"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response.url)
        teacher_user = Usuario.objects.create(nombre_usuario="teacher_test", contrasenia="test")
        teacher_person = Persona.objects.create(id_usuario=teacher_user, dni="30000003", nombre="Doc", apellido="Test", fecha_nacimiento=date(1985, 1, 1))
        Docente.objects.create(id_persona=teacher_person, titulo="Profesor")
        session = self.client.session
        session["usuario_id"] = teacher_user.pk
        session.save()
        response = self.client.post(reverse("gestion-alumno-nuevo"), {})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Alumno.objects.count(), 0)

    def test_staff_views_render_empty_states(self):
        response = self.client.get(reverse("gestion-inicio"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No hay alumnos registrados")
        self.assertContains(response, "No hay docentes registrados")
        self.assertContains(self.client.get(reverse("gestion-academica")), "No hay materias asociadas")

    def test_administrative_dashboard_opens_without_name_errors(self):
        response = self.client.get(reverse("dashboard-administrativo"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('class="btn-gestion"', html)
        self.assertLess(html.index("Gestión de alumnos, docentes y cursos"), html.index('class="btn-logout"'))

    def test_parent_dashboard_opens_with_linked_child(self):
        self.client.logout()
        parent_user = Usuario.objects.create(nombre_usuario="parent_dashboard", contrasenia="test")
        parent_person = Persona.objects.create(id_usuario=parent_user, dni="40000201", nombre="Tutor", apellido="Panel", fecha_nacimiento=date(1980, 1, 1))
        tutor = Tutor.objects.create(id_persona=parent_person)
        child = self.create_student()
        TutorTutoraAlumno.objects.create(id_tutor=tutor, id_alumno=child)
        session = self.client.session
        session["usuario_id"] = parent_user.pk
        session.save()
        response = self.client.get(reverse("dashboard-padres"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, child.id_persona.nombre)

    def test_student_teacher_preceptor_and_director_dashboards_open(self):
        roles = [
            ("alumno", "dashboard-alumno", "50000001", "Alumno", "Test"),
            ("docente", "dashboard-docente", "50000002", "Docente", "Test"),
            ("preceptor", "dashboard-preceptor", "50000003", "Preceptor", "Test"),
            ("directivo", "dashboard-directivo", "50000004", "Directivo", "Test"),
        ]
        student_course = self.course_a
        for username, route_name, dni, nombre, apellido in roles:
            user = Usuario.objects.create(nombre_usuario=username, contrasenia="test")
            person = Persona.objects.create(
                id_usuario=user, dni=dni, nombre=nombre, apellido=apellido,
                fecha_nacimiento=date(2000, 1, 1),
            )
            if username == "alumno":
                Alumno.objects.create(id_persona=person, id_curso=student_course, estado="Activo")
            elif username == "docente":
                Docente.objects.create(id_persona=person, titulo="Profesor")
            elif username == "preceptor":
                preceptor = Preceptor.objects.create(id_persona=person, turno="Mañana", fecha_ingreso=date(2020, 1, 1))
                student_course.legajo_preceptor = preceptor
                student_course.save(update_fields=["legajo_preceptor"])
            else:
                Directivo.objects.create(id_persona=person)
            session = self.client.session
            session["usuario_id"] = user.pk
            session.save()
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200, f"Falló el panel {route_name}: {response.status_code}")

    def test_group_rejects_end_before_start(self):
        group = self.create_group("Natación", starts="10:00", ends="09:00")
        with self.assertRaises(ValidationError):
            group.full_clean()

    def test_sports_allow_two_but_reject_third_and_overlapping_hours(self):
        student = self.create_student()
        first = self.create_group("Natación")
        second = self.create_group("Fútbol", day="Lunes", starts="09:00", ends="10:00")
        third = self.create_group("Vóley", day="Martes", starts="08:00", ends="09:00")
        inscribir_en_deporte(student.pk, first.pk)
        inscribir_en_deporte(student.pk, second.pk)  # Un horario contiguo no se superpone.
        with self.assertRaisesMessage(ReglaNegocioError, "no puede tener más de dos"):
            inscribir_en_deporte(student.pk, third.pk)
        other_student = self.create_student(dni="20000002")
        overlapping = self.create_group("Hockey", day="Lunes", starts="08:30", ends="09:30")
        inscribir_en_deporte(other_student.pk, first.pk)
        with self.assertRaisesMessage(ReglaNegocioError, "superpone"):
            inscribir_en_deporte(other_student.pk, overlapping.pk)

    def test_legacy_sport_fails_closed_until_schedule_is_structured(self):
        from .models import Instalacion
        facility = Instalacion.objects.create(nombre="Patio", capacidad=20, estado="Activo")
        discipline = DisciplinaDeportiva.objects.create(nombre="Tenis", id_instalacion=facility)
        student = self.create_student()
        student.id_disciplina = discipline
        student.save(update_fields=["id_disciplina"])
        group = self.create_group("Ajedrez", day="Martes")
        with self.assertRaisesMessage(ReglaNegocioError, "deporte anterior sin horario estructurado"):
            inscribir_en_deporte(student.pk, group.pk)

    def test_admin_confirmation_converts_legacy_sport_to_a_scheduled_group(self):
        from .models import Instalacion
        facility = Instalacion.objects.create(nombre="Patio", capacidad=20, estado="Activo")
        discipline = DisciplinaDeportiva.objects.create(nombre="Tenis", id_instalacion=facility)
        student = self.create_student()
        student.id_disciplina = discipline
        student.save(update_fields=["id_disciplina"])
        group = self.create_group("Tenis", day="Viernes", starts="14:00", ends="15:00")
        group.disciplina.nombre = "Tenis"
        group.disciplina.save(update_fields=["nombre"])
        group.disciplina_id = discipline.pk
        group.save(update_fields=["disciplina"])
        with self.assertRaisesMessage(ReglaNegocioError, "Confirme con Administración"):
            inscribir_en_deporte(student.pk, group.pk)
        enrollment = inscribir_en_deporte(student.pk, group.pk, confirmar_migracion=True)
        student.refresh_from_db()
        self.assertIsNone(student.id_disciplina_id)
        self.assertEqual(enrollment.grupo_id, group.pk)

    def test_maximum_four_transport_routes_and_active_registration(self):
        routes = [RecorridoTransporte.objects.create(nombre=f"Ruta {i}") for i in range(1, 5)]
        student = self.create_student()
        InscripcionTransporte.objects.create(alumno=student, recorrido=routes[0], estado="Activa")
        response = self.client.post(reverse("gestion-alumno-editar", args=[student.pk]), {
            "dni": "20000001", "nombre": "Ana", "apellido": "Prueba", "fecha_nacimiento": "2015-05-04",
            "curso": self.course_a.pk, "estado": "Activo", "inscripto_comedor": "on", "recorrido": routes[1].pk,
        })
        self.assertRedirects(response, reverse("gestion-inicio"))
        student.refresh_from_db()
        self.assertTrue(student.inscripto_comedor)
        self.assertEqual(list(student.inscripciones_transporte.filter(estado="Activa").values_list("recorrido_id", flat=True)), [routes[1].pk])
        form = __import__("core.business_forms", fromlist=["RecorridoTransporteForm"]).RecorridoTransporteForm({"nombre": "Ruta 5", "descripcion": "", "activo": "on"})
        self.assertFalse(form.is_valid())

    def test_all_eight_report_routes_render_and_admin_can_view_reports(self):
        for code in ["R-01", "R-02", "R-03", "R-04", "R-05", "R-06", "R-07", "R-08"]:
            response = self.client.get(reverse("reportes"), {"reporte": code})
            self.assertEqual(response.status_code, 200, code)
            self.assertContains(response, code)
            self.assertContains(response, "No hay resultados para este reporte")

    def test_non_admin_cannot_view_complete_reports_or_audit(self):
        self.client.logout()
        teacher_user = Usuario.objects.create(nombre_usuario="teacher_report", contrasenia="test")
        teacher_person = Persona.objects.create(id_usuario=teacher_user, dni="30000110", nombre="Doc", apellido="Test", fecha_nacimiento=date(1985, 1, 1))
        Docente.objects.create(id_persona=teacher_person, titulo="Profesor")
        session = self.client.session
        session["usuario_id"] = teacher_user.pk
        session.save()
        self.assertEqual(self.client.get(reverse("reportes"), {"reporte": "R-03"}).status_code, 403)
        self.assertEqual(self.client.get(reverse("auditoria")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reportes"), {"reporte": "R-02"}).status_code, 200)

    def test_parent_report_is_limited_to_linked_child_and_requires_selection(self):
        self.client.logout()
        parent_user = Usuario.objects.create(nombre_usuario="parent_report", contrasenia="test")
        parent_person = Persona.objects.create(id_usuario=parent_user, dni="40000110", nombre="Padre", apellido="Test", fecha_nacimiento=date(1980, 1, 1))
        tutor = Tutor.objects.create(id_persona=parent_person)
        child = self.create_student()
        other = self.create_student(dni="20000004")
        TutorTutoraAlumno.objects.create(id_tutor=tutor, id_alumno=child)
        session = self.client.session
        session["usuario_id"] = parent_user.pk
        session.save()
        response = self.client.get(reverse("reportes"), {"reporte": "R-01"})
        self.assertNotContains(response, f"<td>{child.id_persona.apellido}, {child.id_persona.nombre}</td>")
        response = self.client.get(reverse("reportes"), {"reporte": "R-01", "alumno": child.pk})
        self.assertContains(response, child.id_persona.apellido)
        self.assertNotContains(response, other.id_persona.dni)

    def test_parent_can_manage_only_linked_child_services(self):
        self.client.logout()
        parent_user = Usuario.objects.create(nombre_usuario="parent_services", contrasenia="test")
        parent_person = Persona.objects.create(id_usuario=parent_user, dni="40000111", nombre="Madre", apellido="Test", fecha_nacimiento=date(1980, 1, 1))
        tutor = Tutor.objects.create(id_persona=parent_person)
        child = self.create_student()
        other = self.create_student(dni="20000012")
        TutorTutoraAlumno.objects.create(id_tutor=tutor, id_alumno=child)
        group = self.create_group("Natación")
        session = self.client.session
        session["usuario_id"] = parent_user.pk
        session.save()
        response = self.client.post(reverse("familia-servicios"), {"action": "deporte", "alumno": child.pk, "grupo": group.pk})
        self.assertRedirects(response, reverse("familia-servicios"))
        self.assertTrue(InscripcionDeportiva.objects.filter(alumno=child, grupo=group, estado="Activa").exists())
        response = self.client.post(reverse("familia-servicios"), {"action": "deporte", "alumno": other.pk, "grupo": group.pk})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(InscripcionDeportiva.objects.filter(alumno=other).exists())

    def test_create_user_endpoint_is_server_side_admin_only(self):
        self.client.logout()
        response = self.client.post(reverse("crear-usuario"), {})
        self.assertEqual(response.status_code, 302)
        teacher_user = Usuario.objects.create(nombre_usuario="teacher_create_user", contrasenia="test")
        teacher_person = Persona.objects.create(id_usuario=teacher_user, dni="30000120", nombre="Doc", apellido="Test", fecha_nacimiento=date(1985, 1, 1))
        Docente.objects.create(id_persona=teacher_person, titulo="Profesor")
        session = self.client.session
        session["usuario_id"] = teacher_user.pk
        session.save()
        response = self.client.post(reverse("crear-usuario"), {"dni": "10000002", "nombre_usuario": "otra", "contrasenia": "pass", "correo": "otra@example.invalid"})
        self.assertEqual(response.status_code, 403)

    def test_parent_cannot_submit_payment_or_documents_for_unlinked_student(self):
        self.client.logout()
        parent_user = Usuario.objects.create(nombre_usuario="parent_scope", contrasenia="test")
        parent_person = Persona.objects.create(id_usuario=parent_user, dni="40000990", nombre="Padre", apellido="Scope", fecha_nacimiento=date(1980, 1, 1))
        Tutor.objects.create(id_persona=parent_person)
        unrelated = self.create_student(dni="20000990")
        session = self.client.session
        session["usuario_id"] = parent_user.pk
        session.save()
        payment = self.client.post(reverse("registrar_pago"), {"alumno": unrelated.pk, "mes": "Marzo"})
        documents = self.client.post(reverse("enviar_documentacion"), {"alumno": unrelated.pk})
        self.assertEqual(payment.status_code, 403)
        self.assertEqual(documents.status_code, 403)

    def test_admin_only_reservation_route_rejects_other_roles(self):
        self.client.logout()
        teacher_user = Usuario.objects.create(nombre_usuario="teacher_reservation", contrasenia="test")
        teacher_person = Persona.objects.create(id_usuario=teacher_user, dni="30000991", nombre="Doc", apellido="Reserva", fecha_nacimiento=date(1985, 1, 1))
        Docente.objects.create(id_persona=teacher_person, titulo="Profesor")
        session = self.client.session
        session["usuario_id"] = teacher_user.pk
        session.save()
        response = self.client.post(reverse("crear-reserva"), {})
        self.assertEqual(response.status_code, 403)

    def test_reports_include_current_data_for_each_required_report(self):
        student = self.create_student()
        teacher_person = Persona.objects.create(dni="30000200", nombre="Docente", apellido="Reporte", fecha_nacimiento=date(1985, 1, 1))
        teacher = Docente.objects.create(id_persona=teacher_person, titulo="Profesor")
        subject = Materia.objects.create(nombre="Matemática", descripcion="", carga_horaria=4, cantidad_clases=40)
        CursoCursaMaterias.objects.create(id_curso=self.course_a, id_materia=subject, horarios="Lunes 08:00-10:00")
        DocenteCursoMateria.objects.create(docente=teacher, curso=self.course_a, materia=subject)
        group = self.create_group("Natación", starts="11:00", ends="12:00")
        InscripcionDeportiva.objects.create(alumno=student, grupo=group, estado="Activa")
        route = RecorridoTransporte.objects.create(nombre="Centro")
        InscripcionTransporte.objects.create(alumno=student, recorrido=route, estado="Activa")
        cases = {
            "R-01": ("Comedor", {"alumno": student.pk}),
            "R-02": ("Horario del curso", {"docente": teacher.pk}),
            "R-03": ("Legajo", {"curso": self.course_a.pk}),
            "R-04": ("Matemática", {"materia": subject.pk}),
            "R-05": ("Docentes por nivel", {"docente": teacher.pk}),
            "R-06": ("Natación", {"deporte": group.disciplina_id}),
            "R-07": ("Profesor responsable", {"deporte": group.disciplina_id}),
            "R-08": ("Centro", {"recorrido": route.pk}),
        }
        for code, (expected, params) in cases.items():
            response = self.client.get(reverse("reportes"), {"reporte": code, **params})
            self.assertEqual(response.status_code, 200, code)
            self.assertContains(response, expected, msg_prefix=code)

    def test_audit_callback_records_committed_management_change(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(reverse("gestion-alumno-nuevo"), {
                "dni": "20000011", "nombre": "Auditada", "apellido": "Persona",
                "fecha_nacimiento": "2015-05-04", "curso": self.course_a.pk, "estado": "Activo",
            })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditoriaCambio.objects.filter(entidad="Alumno", accion="crear").exists())
