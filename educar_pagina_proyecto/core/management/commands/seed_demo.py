import datetime
import os
import secrets
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.seguridad import guardar_contrasenia

from core.models import (
    Alumno,
    Arancel,
    Curso,
    Directivo,
    DisciplinaDeportiva,
    Docente,
    DocenteCursoMateria,
    GrupoDeportivo,
    InscripcionDeportiva,
    InscripcionTransporte,
    Instalacion,
    Materia,
    Persona,
    PersonalAdministrativo,
    Preceptor,
    RecorridoTransporte,
    Tutor,
    TutorTutoraAlumno,
    Usuario,
    ValorComedor,
)


class Command(BaseCommand):
    help = "Carga datos de demostración para el sistema web y la app móvil (G2 / RF-M15 y RF-M16)."

    def _clave_nueva(self, usuario):
        """Contrasenia al azar para un usuario de demo. No se escribe en el codigo: se guarda en un archivo local."""
        clave = secrets.token_urlsafe(9)
        self._claves.append((usuario, clave))
        return guardar_contrasenia(clave)

    def handle(self, *args, **options):
        # Freno: solo se siembra sobre una base vacía. Así nunca se mezcla con datos reales.
        if Persona.objects.exists():
            raise CommandError(
                "La base ya tiene personas cargadas, así que seed_demo no se ejecuta "
                "para no mezclar datos de demostración con datos reales. "
                "Para una demo, usá una base vacía."
            )
        self.stdout.write(self.style.NOTICE("Iniciando carga de datos demo..."))
        self._claves = []
        ya_existian = set(Usuario.objects.values_list("nombre_usuario", flat=True))

        with transaction.atomic():
            # 1. Aranceles por nivel (RF-M15)
            aranceles_datos = [
                ("Inicial", 48000.00),
                ("Primario", 25000.00),
                ("Secundario", 32000.00),
            ]
            # Solo crea los aranceles que falten: si ya existen, se respetan sus montos.
            for nivel, monto in aranceles_datos:
                Arancel.objects.get_or_create(
                    nivel=nivel,
                    defaults={"monto": monto},
                )
            self.stdout.write(self.style.SUCCESS("[OK] Aranceles configurados."))

            # 2. Los cuatro recorridos de transporte obligatorios
            recorridos_datos = [
                ("Recorrido Norte", "Av. San Martín, Belgrano, Plaza Central, Instituto"),
                ("Recorrido Sur", "Av. Rivadavia, Estación FFCC, Hospital Regional, Instituto"),
                ("Recorrido Este", "Ruta 3, Barrio Jardín, Polideportivo, Instituto"),
                ("Recorrido Oeste", "Av. Mitre, Parque Industrial, Barrio Los Álamos, Instituto"),
            ]
            recorridos_creados = {}
            for nombre, desc in recorridos_datos:
                rec, _ = RecorridoTransporte.objects.get_or_create(
                    nombre=nombre,
                    defaults={"descripcion": desc, "activo": True},
                )
                recorridos_creados[nombre] = rec
            # Valores de demostración (RF-M15); si ya tienen valor, no se pisan.
            for rec in recorridos_creados.values():
                if rec.valor is None:
                    rec.valor = Decimal("15000.00")
                    rec.save(update_fields=["valor"])
            if not ValorComedor.objects.exists():
                ValorComedor.objects.create(monto=Decimal("12000.00"))
            self.stdout.write(self.style.SUCCESS("[OK] 4 Recorridos de transporte listos."))

            # 3. Instalaciones deportivas
            gimnasio, _ = Instalacion.objects.get_or_create(
                nombre="Gimnasio Polideportivo Central",
                defaults={"capacidad": 120, "estado": "Disponible"},
            )
            cancha, _ = Instalacion.objects.get_or_create(
                nombre="Cancha de Césped Sintético",
                defaults={"capacidad": 50, "estado": "Disponible"},
            )

            # 4. Disciplinas deportivas
            disciplinas = {}
            for disc_nom in ["Fútbol", "Básquet", "Vóley", "Atletismo"]:
                inst = cancha if disc_nom == "Fútbol" else gimnasio
                d, _ = DisciplinaDeportiva.objects.get_or_create(
                    nombre=disc_nom,
                    defaults={"horarios": "Tarde", "id_instalacion": inst},
                )
                if d.valor is None:
                    d.valor = Decimal("8000.00")
                    d.save(update_fields=["valor"])
                disciplinas[disc_nom] = d
            self.stdout.write(self.style.SUCCESS("[OK] Disciplinas e instalaciones listas."))

            # 5. Usuarios y Personas por cada rol
            # 5.1 Personal Administrativo
            u_admin, _ = Usuario.objects.get_or_create(
                nombre_usuario="admin_demo",
                defaults={"correo": "admin@educar.edu.ar", "contrasenia": self._clave_nueva("admin_demo")},
            )
            p_admin, _ = Persona.objects.get_or_create(
                dni="30111222",
                defaults={
                    "nombre": "Mariana",
                    "apellido": "López",
                    "email": "admin@educar.edu.ar",
                    "telefono": "1140001111",
                    "fecha_nacimiento": "1985-04-12",
                    "direccion": "Av. Colón 450",
                    "id_usuario": u_admin,
                },
            )
            PersonalAdministrativo.objects.get_or_create(
                id_persona=p_admin,
                defaults={
                    "sector": "Administración Central",
                    "cargo": "Responsable de Gestión",
                    "fecha_ingreso": "2020-03-01",
                },
            )

            # 5.2 Directivo
            u_dir, _ = Usuario.objects.get_or_create(
                nombre_usuario="directivo_demo",
                defaults={"correo": "directivo@educar.edu.ar", "contrasenia": self._clave_nueva("directivo_demo")},
            )
            p_dir, _ = Persona.objects.get_or_create(
                dni="22333444",
                defaults={
                    "nombre": "Roberto",
                    "apellido": "Alonso",
                    "email": "directivo@educar.edu.ar",
                    "telefono": "1140002222",
                    "fecha_nacimiento": "1972-08-20",
                    "direccion": "San Martín 1200",
                    "id_usuario": u_dir,
                },
            )
            Directivo.objects.get_or_create(
                id_persona=p_dir,
            )

            # 5.3 Preceptor
            u_prec, _ = Usuario.objects.get_or_create(
                nombre_usuario="preceptor_demo",
                defaults={"correo": "preceptor@educar.edu.ar", "contrasenia": self._clave_nueva("preceptor_demo")},
            )
            p_prec, _ = Persona.objects.get_or_create(
                dni="32444555",
                defaults={
                    "nombre": "Esteban",
                    "apellido": "Ríos",
                    "email": "preceptor@educar.edu.ar",
                    "telefono": "1140003333",
                    "fecha_nacimiento": "1988-11-15",
                    "direccion": "Belgrano 880",
                    "id_usuario": u_prec,
                },
            )
            Preceptor.objects.get_or_create(
                id_persona=p_prec,
                defaults={
                    "turno": "Tarde",
                    "fecha_ingreso": "2021-03-01",
                },
            )

            # 5.4 Docente (profesor de deportes y materias)
            u_doc, _ = Usuario.objects.get_or_create(
                nombre_usuario="docente_demo",
                defaults={"correo": "profesor@educar.edu.ar", "contrasenia": self._clave_nueva("docente_demo")},
            )
            p_doc, _ = Persona.objects.get_or_create(
                dni="28555666",
                defaults={
                    "nombre": "Carlos",
                    "apellido": "Martínez",
                    "email": "profesor@educar.edu.ar",
                    "telefono": "1140004444",
                    "fecha_nacimiento": "1982-01-25",
                    "direccion": "Mitre 320",
                    "id_usuario": u_doc,
                },
            )
            docente, _ = Docente.objects.get_or_create(
                id_persona=p_doc,
                defaults={
                    "titulo": "Profesor Nacional de Educación Física",
                    "especialidad": "Deportes Colectivos",
                    "fecha_ingreso": "2019-02-15",
                    "estado": "Activo",
                },
            )

            # 5.5 Tutor
            u_tutor, _ = Usuario.objects.get_or_create(
                nombre_usuario="tutor_demo",
                defaults={"correo": "tutor@familia.com", "contrasenia": self._clave_nueva("tutor_demo")},
            )
            p_tutor, _ = Persona.objects.get_or_create(
                dni="27666777",
                defaults={
                    "nombre": "Martín",
                    "apellido": "Romero",
                    "email": "tutor@familia.com",
                    "telefono": "1155558888",
                    "fecha_nacimiento": "1980-06-10",
                    "direccion": "Calle Ombú 742",
                    "id_usuario": u_tutor,
                },
            )
            tutor, _ = Tutor.objects.get_or_create(id_persona=p_tutor)

            # 5.6 Curso y Materia para asignaciones académicas
            curso_sec1, _ = Curso.objects.get_or_create(
                comision="1A",
                anio=1,
                nivel="Secundario",
                defaults={"turno": "Mañana", "cupo_maximo": 30},
            )
            curso_prim5, _ = Curso.objects.get_or_create(
                comision="5B",
                anio=5,
                nivel="Primario",
                defaults={"turno": "Tarde", "cupo_maximo": 30},
            )

            # Nivel Inicial (salas de 3, 4 y 5 años = años 1 a 3), necesario para aprobar
            # solicitudes de inscripción de ese nivel.
            for anio_sala in (1, 2, 3):
                Curso.objects.get_or_create(
                    comision="A",
                    anio=anio_sala,
                    nivel="Inicial",
                    defaults={"turno": "Mañana", "cupo_maximo": 20},
                )

            materia_edfis, _ = Materia.objects.get_or_create(
                nombre="Educación Física",
                defaults={
                    "descripcion": "Desarrollo corporal y deportivo",
                    "carga_horaria": 4,
                    "cantidad_clases": 32,
                },
            )

            DocenteCursoMateria.objects.get_or_create(
                docente=docente,
                curso=curso_sec1,
                materia=materia_edfis,
            )
            self.stdout.write(self.style.SUCCESS("[OK] Usuarios, roles y asignación académica listos."))

            # 5.7 Dos Alumnos hijos del Tutor
            u_al1, _ = Usuario.objects.get_or_create(
                nombre_usuario="alumno_demo1",
                defaults={"correo": "alumno1@familia.com", "contrasenia": self._clave_nueva("alumno_demo1")},
            )
            p_al1, _ = Persona.objects.get_or_create(
                dni="48111001",
                defaults={
                    "nombre": "Lucas",
                    "apellido": "Romero",
                    "email": "alumno1@familia.com",
                    "fecha_nacimiento": "2011-03-14",
                    "direccion": "Calle Ombú 742",
                    "id_usuario": u_al1,
                },
            )
            alumno1, _ = Alumno.objects.get_or_create(
                id_persona=p_al1,
                defaults={
                    "estado": "Activo",
                    "id_curso": curso_sec1,
                    "inscripto_comedor": True,
                    "fecha_ingreso": "2024-03-01",
                },
            )
            TutorTutoraAlumno.objects.get_or_create(
                id_tutor=tutor,
                id_alumno=alumno1,
                defaults={"tipo_parentesco": "Padre"},
            )

            u_al2, _ = Usuario.objects.get_or_create(
                nombre_usuario="alumno_demo2",
                defaults={"correo": "alumno2@familia.com", "contrasenia": self._clave_nueva("alumno_demo2")},
            )
            p_al2, _ = Persona.objects.get_or_create(
                dni="50222002",
                defaults={
                    "nombre": "Valentina",
                    "apellido": "Romero",
                    "email": "alumno2@familia.com",
                    "fecha_nacimiento": "2014-07-22",
                    "direccion": "Calle Ombú 742",
                    "id_usuario": u_al2,
                },
            )
            alumno2, _ = Alumno.objects.get_or_create(
                id_persona=p_al2,
                defaults={
                    "estado": "Activo",
                    "id_curso": curso_prim5,
                    "inscripto_comedor": False,
                    "fecha_ingreso": "2024-03-01",
                },
            )
            TutorTutoraAlumno.objects.get_or_create(
                id_tutor=tutor,
                id_alumno=alumno2,
                defaults={"tipo_parentesco": "Padre"},
            )
            self.stdout.write(self.style.SUCCESS("[OK] Alumnos vinculados al Tutor creados."))

            # 6. Grupos Deportivos con horarios no superpuestos
            grupos_def = [
                (disciplinas["Fútbol"], "Secundario", "Lunes", datetime.time(14, 0), datetime.time(15, 30)),
                (disciplinas["Fútbol"], "Primario", "Miércoles", datetime.time(15, 30), datetime.time(17, 0)),
                (disciplinas["Básquet"], "Secundario", "Martes", datetime.time(16, 0), datetime.time(17, 30)),
                (disciplinas["Vóley"], "Primario", "Jueves", datetime.time(14, 30), datetime.time(16, 0)),
                (disciplinas["Atletismo"], "Secundario", "Viernes", datetime.time(15, 0), datetime.time(16, 30)),
            ]
            grupos_inst = []
            for disc, niv, dia, ini, fin in grupos_def:
                grp, _ = GrupoDeportivo.objects.get_or_create(
                    disciplina=disc,
                    nivel=niv,
                    dia_semana=dia,
                    hora_inicio=ini,
                    hora_fin=fin,
                    defaults={"profesor_responsable": docente},
                )
                grupos_inst.append(grp)
            self.stdout.write(self.style.SUCCESS("[OK] Grupos deportivos organizados."))

            # 7. Inscripciones iniciales para probar la app móvil
            # Lucas participa en Fútbol y tiene Recorrido Norte
            InscripcionDeportiva.objects.get_or_create(
                alumno=alumno1,
                grupo=grupos_inst[0],
                defaults={"estado": "Activa"},
            )
            InscripcionTransporte.objects.get_or_create(
                alumno=alumno1,
                recorrido=recorridos_creados["Recorrido Norte"],
                defaults={"estado": "Activa"},
            )

            # Valentina participa en Vóley
            InscripcionDeportiva.objects.get_or_create(
                alumno=alumno2,
                grupo=grupos_inst[3],
                defaults={"estado": "Activa"},
            )

        self.stdout.write(self.style.SUCCESS("=== SEED DEMO COMPLETADO CON EXITO ==="))
        # Las contrasenias no se imprimen: se guardan en un archivo local (ignorado por git).
        nuevas = [(usuario, clave) for usuario, clave in self._claves if usuario not in ya_existian]
        ruta = getattr(settings, "SEED_CREDENCIALES_PATH", None) or os.path.join(settings.BASE_DIR, ".env.demo-cuentas")
        with open(ruta, "w", encoding="utf-8") as archivo:
            archivo.write("# Contrasenias de la demo generadas por seed_demo. Archivo local, ignorado por git.\n")
            for usuario, clave in nuevas:
                archivo.write(f"{usuario}: {clave}\n")
        self.stdout.write("Usuarios de prueba creados: " + ", ".join(usuario for usuario, _ in nuevas))
        self.stdout.write(f"Contrasenias guardadas en {ruta} (no se muestran en pantalla).")
