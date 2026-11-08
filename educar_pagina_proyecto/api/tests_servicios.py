import datetime
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import (
    Alumno,
    PersonalAdministrativo,
    Curso,
    DisciplinaDeportiva,
    Docente,
    GrupoDeportivo,
    InscripcionDeportiva,
    InscripcionTransporte,
    Instalacion,
    Noticia,
    Persona,
    RecorridoTransporte,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
)


class ServiciosAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        # Crear instalación
        self.instalacion = Instalacion.objects.create(
            nombre="Gimnasio Central",
            capacidad=50,
            estado="Disponible",
        )

        # Crear Disciplinas
        self.futbol = DisciplinaDeportiva.objects.create(
            nombre="Fútbol",
            horarios="Lunes y Miércoles 14:00 - 15:30",
            id_instalacion=self.instalacion,
        )
        self.basquet = DisciplinaDeportiva.objects.create(
            nombre="Básquet",
            horarios="Lunes y Miércoles 16:00 - 17:30",
            id_instalacion=self.instalacion,
        )
        self.natacion = DisciplinaDeportiva.objects.create(
            nombre="Natación",
            horarios="Martes y Jueves 10:00 - 11:30",
            id_instalacion=self.instalacion,
        )

        # Crear Docente
        self.persona_doc = Persona.objects.create(
            nombre="Carlos",
            apellido="Entrenador",
            dni="20111222",
            email="carlos@colegio.edu.ar",
            telefono="1122334455",
            fecha_nacimiento="1980-05-15",
            direccion="Calle Falsa 123",
        )
        self.docente = Docente.objects.create(
            id_persona=self.persona_doc,
            titulo="Profesor de Educación Física",
            estado="Activo",
        )

        # Crear Grupos Deportivos
        self.grupo_futbol = GrupoDeportivo.objects.create(
            disciplina=self.futbol,
            nivel="Secundario",
            dia_semana="Lunes",
            hora_inicio=datetime.time(14, 0),
            hora_fin=datetime.time(15, 30),
            profesor_responsable=self.docente,
        )
        self.grupo_basquet = GrupoDeportivo.objects.create(
            disciplina=self.basquet,
            nivel="Secundario",
            dia_semana="Lunes",
            hora_inicio=datetime.time(16, 0),
            hora_fin=datetime.time(17, 30),
            profesor_responsable=self.docente,
        )
        self.grupo_futbol_conflicto = GrupoDeportivo.objects.create(
            disciplina=self.basquet,
            nivel="Secundario",
            dia_semana="Lunes",
            hora_inicio=datetime.time(14, 30),  # Se superpone con fútbol (14:00 - 15:30)
            hora_fin=datetime.time(16, 0),
            profesor_responsable=self.docente,
        )
        self.grupo_natacion = GrupoDeportivo.objects.create(
            disciplina=self.natacion,
            nivel="Secundario",
            dia_semana="Martes",
            hora_inicio=datetime.time(10, 0),
            hora_fin=datetime.time(11, 30),
            profesor_responsable=self.docente,
        )

        # Crear Recorridos de Transporte
        self.recorrido_norte = RecorridoTransporte.objects.create(
            nombre="Recorrido Norte",
            descripcion="Paradas: Av. San Martín, Belgrano y Plaza Central",
            activo=True,
        )
        self.recorrido_sur = RecorridoTransporte.objects.create(
            nombre="Recorrido Sur",
            descripcion="Paradas: Av. Rivadavia, Estación y Hospital",
            activo=True,
        )

        # Tutor 1 y su hijo
        self.user_tutor1 = Usuario.objects.create(
            nombre_usuario="tutor1",
            correo="tutor1@test.com",
            contrasenia="clave123",
        )
        self.persona_tutor1 = Persona.objects.create(
            nombre="Juan",
            apellido="Pérez",
            dni="25000111",
            email="tutor1@test.com",
            telefono="1144556677",
            fecha_nacimiento="1975-01-01",
            direccion="Calle 1",
            id_usuario=self.user_tutor1,
        )
        self.tutor1 = Tutor.objects.create(id_persona=self.persona_tutor1)

        self.user_hijo1 = Usuario.objects.create(
            nombre_usuario="alumno1",
            correo="alumno1@test.com",
            contrasenia="clave123",
        )
        self.persona_hijo1 = Persona.objects.create(
            nombre="Mateo",
            apellido="Pérez",
            dni="45000111",
            email="alumno1@test.com",
            fecha_nacimiento="2010-02-02",
            direccion="Calle 1",
            id_usuario=self.user_hijo1,
        )
        self.alumno1 = Alumno.objects.create(
            id_persona=self.persona_hijo1,
            estado="Activo",
        )
        TutorTutoraAlumno.objects.create(
            id_tutor=self.tutor1,
            id_alumno=self.alumno1,
            tipo_parentesco="Padre",
        )

        # Tutor 2 y su hijo (para pruebas de permisos y aislamiento)
        self.user_tutor2 = Usuario.objects.create(
            nombre_usuario="tutor2",
            correo="tutor2@test.com",
            contrasenia="clave123",
        )
        self.persona_tutor2 = Persona.objects.create(
            nombre="Laura",
            apellido="Gómez",
            dni="26000222",
            email="tutor2@test.com",
            telefono="1199887766",
            fecha_nacimiento="1978-03-03",
            direccion="Calle 2",
            id_usuario=self.user_tutor2,
        )
        self.tutor2 = Tutor.objects.create(id_persona=self.persona_tutor2)

        self.user_hijo2 = Usuario.objects.create(
            nombre_usuario="alumno2",
            correo="alumno2@test.com",
            contrasenia="clave123",
        )
        self.persona_hijo2 = Persona.objects.create(
            nombre="Sofía",
            apellido="Gómez",
            dni="46000222",
            email="alumno2@test.com",
            fecha_nacimiento="2011-04-04",
            direccion="Calle 2",
            id_usuario=self.user_hijo2,
        )
        self.alumno2 = Alumno.objects.create(
            id_persona=self.persona_hijo2,
            estado="Activo",
        )
        TutorTutoraAlumno.objects.create(
            id_tutor=self.tutor2,
            id_alumno=self.alumno2,
            tipo_parentesco="Madre",
        )

    def _token(self, usuario):
        refresh = RefreshToken()
        refresh['user_id'] = usuario.id
        refresh['nombre_usuario'] = usuario.nombre_usuario
        return str(refresh.access_token)

    def test_perfil_patch_actualiza_email_y_telefono(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-perfil")
        response = self.client.patch(url, {
            "email": "nuevo_email@test.com",
            "telefono": "1199998888",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.persona_tutor1.refresh_from_db()
        self.assertEqual(self.persona_tutor1.email, "nuevo_email@test.com")
        self.assertEqual(self.persona_tutor1.telefono, "1199998888")

    def test_perfil_patch_valida_email_invalido(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-perfil")
        response = self.client.patch(url, {
            "email": "correo-no-valido",
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_servicios_listar_alumnos_tutor(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-servicios-alumnos")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Solo debe ver a Mateo (su hijo), no a Sofía
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.alumno1.pk)
        self.assertEqual(response.data[0]["nombre"], "Mateo")

    def test_servicios_tutor_no_puede_acceder_hijo_ajeno(self):
        # Tutor 1 intenta acceder a servicios de Sofía (hija de Tutor 2)
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-servicios-mis-servicios") + f"?alumno={self.alumno2.pk}"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("error", response.data)

    def test_servicios_inscribir_deporte_exitoso(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-servicios-deportes-inscribir")
        response = self.client.post(url, {
            "alumno_id": self.alumno1.pk,
            "grupo_id": self.grupo_futbol.pk,
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(InscripcionDeportiva.objects.filter(
            alumno=self.alumno1, grupo=self.grupo_futbol, estado="Activa"
        ).exists())

    def test_servicios_inscribir_deporte_conflicto_horario(self):
        # Inscribir primero en fútbol (Lunes 14:00 - 15:30)
        InscripcionDeportiva.objects.create(
            alumno=self.alumno1, grupo=self.grupo_futbol, estado="Activa"
        )

        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Intentar inscribir en grupo que se superpone (Lunes 14:30 - 16:00)
        url = reverse("api-servicios-deportes-inscribir")
        response = self.client.post(url, {
            "alumno_id": self.alumno1.pk,
            "grupo_id": self.grupo_futbol_conflicto.pk,
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("superpone", response.data["error"])

    def test_servicios_inscribir_deporte_maximo_dos(self):
        # Inscribir en 2 deportes permitidos
        InscripcionDeportiva.objects.create(
            alumno=self.alumno1, grupo=self.grupo_futbol, estado="Activa"
        )
        InscripcionDeportiva.objects.create(
            alumno=self.alumno1, grupo=self.grupo_basquet, estado="Activa"
        )

        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Intentar un 3er deporte
        url = reverse("api-servicios-deportes-inscribir")
        response = self.client.post(url, {
            "alumno_id": self.alumno1.pk,
            "grupo_id": self.grupo_natacion.pk,
        }, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("más de dos deportes", response.data["error"])

    def test_servicios_desinscribir_deporte(self):
        ins = InscripcionDeportiva.objects.create(
            alumno=self.alumno1, grupo=self.grupo_futbol, estado="Activa"
        )

        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-servicios-deportes-desinscribir", args=[ins.pk])
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ins.refresh_from_db()
        self.assertEqual(ins.estado, "Finalizada")

    def test_servicios_transporte_asignar_y_retirar(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Asignar transporte Norte
        url = reverse("api-servicios-transporte-inscripcion")
        res_asignar = self.client.put(url, {
            "alumno_id": self.alumno1.pk,
            "recorrido_id": self.recorrido_norte.pk,
        }, format="json")
        self.assertEqual(res_asignar.status_code, status.HTTP_200_OK)
        self.assertTrue(InscripcionTransporte.objects.filter(
            alumno=self.alumno1, recorrido=self.recorrido_norte, estado="Activa"
        ).exists())

        # Retirar transporte (recorrido_id = None)
        res_retirar = self.client.put(url, {
            "alumno_id": self.alumno1.pk,
            "recorrido_id": None,
        }, format="json")
        self.assertEqual(res_retirar.status_code, status.HTTP_200_OK)
        self.assertFalse(InscripcionTransporte.objects.filter(
            alumno=self.alumno1, estado="Activa"
        ).exists())

    def test_servicios_comedor_activar_desactivar(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = reverse("api-servicios-comedor")
        # Activar
        res_activar = self.client.put(url, {
            "alumno_id": self.alumno1.pk,
            "inscripto": True,
        }, format="json")
        self.assertEqual(res_activar.status_code, status.HTTP_200_OK)
        self.alumno1.refresh_from_db()
        self.assertTrue(self.alumno1.inscripto_comedor)

        # Desactivar
        res_desactivar = self.client.put(url, {
            "alumno_id": self.alumno1.pk,
            "inscripto": False,
        }, format="json")
        self.assertEqual(res_desactivar.status_code, status.HTTP_200_OK)
        self.alumno1.refresh_from_db()
        self.assertFalse(self.alumno1.inscripto_comedor)

    def test_servicios_offline_bundle(self):
        token = self._token(self.user_tutor1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        persona_admin = Persona.objects.create(
            nombre="Admin",
            apellido="General",
            dni="20999888",
            email="admin@test.com",
            fecha_nacimiento="1985-01-01",
            direccion="Colegio 123",
        )
        admin = PersonalAdministrativo.objects.create(
            id_persona=persona_admin,
            sector="Dirección",
            cargo="Secretario",
            fecha_ingreso=datetime.date.today(),
        )
        Noticia.objects.create(
            titulo="Inicio de Actividades Deportivas",
            contenido="Se encuentran abiertas las inscripciones.",
            fecha_publicacion=datetime.date.today(),
            legajo_personal=admin,
        )

        url = reverse("api-servicios-offline-bundle")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("sincronizado_en", response.data)
        self.assertIn("usuario", response.data)
        self.assertIn("alumnos", response.data)
        self.assertIn("catalogo_deportes", response.data)
        self.assertIn("catalogo_transporte", response.data)
        self.assertIn("comunicados", response.data)
        self.assertEqual(len(response.data["alumnos"]), 1)
        self.assertEqual(response.data["alumnos"][0]["id"], self.alumno1.pk)
