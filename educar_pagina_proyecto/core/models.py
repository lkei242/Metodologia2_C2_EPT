# Modelos del sistema de gestión escolar Educar para Transformar.
from django.db import models
from django.db.models import Q


class Alumno(models.Model):
    ESTADOS = [("Activo", "Activo"), ("Inactivo", "Inactivo")]
    legajo = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Activo")
    inscripto_comedor = models.BooleanField(default=False)
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')
    fecha_ingreso = models.DateField(blank=True, null=True)
    id_disciplina = models.ForeignKey(
        'DisciplinaDeportiva',
        models.DO_NOTHING,
        db_column='id_disciplina',
        blank=True,
        null=True,
    )
    id_curso = models.ForeignKey('Curso', models.DO_NOTHING, db_column='id_curso', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'alumno'

    def __str__(self):
        return f"{self.legajo} - {self.id_persona}"

class Asistencia(models.Model):
    id_asistencia = models.AutoField(primary_key=True)

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    fecha = models.DateField(
        blank=True,
        null=True
    )

    tipo_asistencia = models.CharField(
        max_length=10,
        choices=[
            ('Presente', 'Presente'),
            ('Ausente', 'Ausente'),
            ('Tardanza', 'Tardanza')
        ]
    )

    archivo_justificacion = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    observacion = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'asistencia'

    def __str__(self):
        return f"{self.legajo_alumno} - {self.fecha} - {self.tipo_asistencia}"


class Aula(models.Model):
    id_aula = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    numero = models.IntegerField(blank=True, null=True)
    piso = models.IntegerField(blank=True, null=True)
    capacidad = models.IntegerField()
    tipo = models.CharField(max_length=50, blank=True, null=True)
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'aula'


class Calificacion(models.Model):
    id_calificacion = models.AutoField(primary_key=True)
    nota = models.DecimalField(max_digits=4, decimal_places=2)
    tipo_evaluacion = models.CharField(max_length=50, blank=True, null=True)
    fecha = models.DateField()
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')
    legajo_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='legajo_alumno')

    class Meta:
        managed = True
        db_table = 'calificacion'


class Cuota(models.Model):
    id_cuota = models.AutoField(primary_key=True)

    periodo = models.CharField(max_length=20)

    monto = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )
    fecha_pago = models.DateField(blank=True, null=True)
    fecha_vencimiento = models.DateField(blank=True, null=True)
    medio_pago = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )
    estado = models.CharField(
        max_length=30,
        default='Pendiente'
    )
    id_tutor = models.ForeignKey(
        'Tutor',
        models.DO_NOTHING,
        db_column='id_tutor'
    )
    id_legajo_alumno = models.ForeignKey(
        'Alumno',
        models.DO_NOTHING,
        db_column='id_legajo_alumno'
    )

    class Meta:
        managed = True
        db_table = 'cuota'

class Curso(models.Model):
    id_curso = models.AutoField(primary_key=True, db_column='id')
    comision = models.CharField(max_length=20)
    anio = models.IntegerField()
    turno = models.CharField(max_length=30)
    nivel = models.CharField(max_length=30)
    cupo_maximo = models.IntegerField(blank=True, null=True)
    legajo_preceptor = models.ForeignKey('Preceptor', models.DO_NOTHING, db_column='legajo_preceptor', blank=True, null=True)
    id_aula = models.ForeignKey(Aula, models.DO_NOTHING, db_column='id_aula', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'curso'


class CursoCursaMaterias(models.Model):
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')
    horarios = models.TextField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'curso_cursa_materias'


class CursoParticipaViaje(models.Model):
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    id_viaje = models.ForeignKey('Viaje', models.DO_NOTHING, db_column='id_viaje')

    class Meta:
        managed = True
        db_table = 'curso_participa_viaje'


class Directivo(models.Model):
    id = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')

    class Meta:
        managed = True
        db_table = 'directivo'


class DisciplinaDeportiva(models.Model):
    id_disciplina = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    horarios = models.TextField(blank=True, null=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    id_instalacion = models.ForeignKey(
        'Instalacion',
        models.DO_NOTHING,
        db_column='id_instalacion',
    )

    class Meta:
        managed = True
        db_table = 'disciplina_deportiva'

    def __str__(self):
        return self.nombre


class Docente(models.Model):
    ESTADOS = [("Activo", "Activo"), ("Inactivo", "Inactivo")]
    legajo = models.AutoField(primary_key=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Activo")
    id_persona = models.ForeignKey('Persona', models.DO_NOTHING, db_column='id_persona')
    titulo = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=100, blank=True, null=True)
    fecha_ingreso = models.DateField(blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'docente'


class DocenteDictaMateria(models.Model):
    id_docente = models.ForeignKey(Docente, models.DO_NOTHING, db_column='id_docente')
    id_materia = models.ForeignKey('Materia', models.DO_NOTHING, db_column='id_materia')

    class Meta:
        managed = True
        db_table = 'docente_dicta_materia'


class DocenteCursoMateria(models.Model):
    docente = models.ForeignKey(Docente, on_delete=models.PROTECT, related_name='asignaciones_academicas')
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name='asignaciones_docentes')
    materia = models.ForeignKey('Materia', on_delete=models.PROTECT, related_name='asignaciones_docentes')

    class Meta:
        db_table = 'docente_curso_materia'
        constraints = [
            models.UniqueConstraint(fields=['docente', 'curso', 'materia'], name='uniq_docente_curso_materia'),
        ]

    def __str__(self):
        return f"{self.docente} - {self.materia} - {self.curso}"


class GrupoDeportivo(models.Model):
    DIAS = [(d, d) for d in ("Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo")]
    disciplina = models.ForeignKey(DisciplinaDeportiva, on_delete=models.PROTECT, related_name="grupos")
    nivel = models.CharField(max_length=30)
    dia_semana = models.CharField(max_length=12, choices=DIAS)
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    profesor_responsable = models.ForeignKey(Docente, on_delete=models.PROTECT, related_name="grupos_deportivos")

    class Meta:
        db_table = "grupo_deportivo"
        constraints = [models.UniqueConstraint(fields=["disciplina", "nivel", "dia_semana", "hora_inicio", "hora_fin"], name="uniq_grupo_deportivo_horario")]
        ordering = ["disciplina__nombre", "nivel", "dia_semana", "hora_inicio"]

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.hora_inicio and self.hora_fin and self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "La hora de fin debe ser posterior al inicio."})

    def __str__(self):
        return f"{self.disciplina} - {self.nivel} - {self.dia_semana} {self.hora_inicio:%H:%M}"


class InscripcionDeportiva(models.Model):
    ESTADOS = [("Activa", "Activa"), ("Finalizada", "Finalizada")]
    alumno = models.ForeignKey(Alumno, on_delete=models.PROTECT, related_name="inscripciones_deportivas")
    grupo = models.ForeignKey(GrupoDeportivo, on_delete=models.PROTECT, related_name="inscripciones")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Activa")
    fecha_inscripcion = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "inscripcion_deportiva"
        constraints = [models.UniqueConstraint(fields=["alumno", "grupo"], condition=Q(estado="Activa"), name="uniq_inscripcion_deportiva_activa")]


class RecorridoTransporte(models.Model):
    nombre = models.CharField(max_length=40, unique=True)
    descripcion = models.CharField(max_length=200, blank=True)
    valor = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    activo = models.BooleanField(default=True)

    class Meta:
        db_table = "recorrido_transporte"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class InscripcionTransporte(models.Model):
    ESTADOS = [("Activa", "Activa"), ("Finalizada", "Finalizada")]
    alumno = models.ForeignKey(Alumno, on_delete=models.PROTECT, related_name="inscripciones_transporte")
    recorrido = models.ForeignKey(RecorridoTransporte, on_delete=models.PROTECT, related_name="inscripciones")
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Activa")
    fecha_inscripcion = models.DateField(auto_now_add=True)

    class Meta:
        db_table = "inscripcion_transporte"
        constraints = [models.UniqueConstraint(fields=["alumno"], condition=Q(estado="Activa"), name="uniq_transporte_activo_por_alumno")]


class AuditoriaCambio(models.Model):
    usuario = models.ForeignKey("Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="cambios_auditados")
    fecha = models.DateTimeField(auto_now_add=True)
    entidad = models.CharField(max_length=80)
    registro_id = models.CharField(max_length=80)
    accion = models.CharField(max_length=30)
    campos = models.JSONField(default=list)

    class Meta:
        db_table = "auditoria_cambio"
        ordering = ["-fecha", "-pk"]


class DocenteDisciplina(models.Model):
    id = models.AutoField(primary_key=True)

    legajo_docente = models.ForeignKey(
        Docente,
        models.DO_NOTHING,
        db_column='legajo_docente',
    )

    id_disciplina = models.ForeignKey(
        DisciplinaDeportiva,
        models.DO_NOTHING,
        db_column='id_disciplina',
    )

    class Meta:
        managed = True
        db_table = 'docente_disciplina'

class Evaluacion(models.Model):
    id_evaluacion = models.AutoField(primary_key=True)

    alumno = models.ForeignKey(
        'Alumno',
        on_delete=models.CASCADE,
        db_column='legajo_alumno'
    )

    docente = models.ForeignKey(
        'Docente',
        on_delete=models.CASCADE,
        db_column='legajo_docente'
    )

    materia = models.ForeignKey(
        'Materia',
        on_delete=models.CASCADE,
        db_column='id_materia'
    )

    tipo = models.CharField(max_length=50)

    nota = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True
    )

    fecha = models.DateField()

    observacion = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.alumno} - {self.materia} - {self.nota}"

class Tarea(models.Model):
    id = models.AutoField(primary_key=True)
    
    docente = models.ForeignKey(
        'Docente', 
        on_delete=models.CASCADE,
        db_column='legajo_docente'
    )
    
    materia = models.ForeignKey(
        'Materia',
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )
    
    tipo = models.CharField(
        max_length=50,
        choices=[
            ('Tarea', 'Tarea'),
            ('Evaluación', 'Evaluación')
        ]
    )
    
    titulo = models.CharField(max_length=200)
    descripcion = models.TextField()
    fecha = models.DateField(null=True, blank=True)
    
    curso_destinado = models.ForeignKey(
        Curso,
        on_delete=models.CASCADE,
        related_name='tareas_docente'
    )
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_publicacion = models.DateTimeField(blank=True, null=True)
    programa_publicacion = models.BooleanField(default=False)
    
    estado = models.CharField(
        max_length=20,
        choices=[
            ('Borrador', 'Borrador'),
            ('Publicado', 'Publicado'),
            ('Programado', 'Programado')
        ],
        default='Borrador'
    )
    
    def __str__(self):
        return f"{self.titulo} - {self.estado}"

    class Meta:
        db_table = 'tarea'

class Inscripcion(models.Model):
    id_inscripcion = models.AutoField(primary_key=True)
    fecha_inscripcion = models.DateField()
    estado = models.CharField(max_length=30)
    id_curso = models.ForeignKey(Curso, models.DO_NOTHING, db_column='id_curso')
    legajo_alumno = models.ForeignKey(Alumno, models.DO_NOTHING, db_column='legajo_alumno')

    class Meta:
        managed = True
        db_table = 'inscripcion'
        constraints = [
            models.UniqueConstraint(
                fields=['legajo_alumno'],
                condition=Q(estado='Activa'),
                name='uniq_inscripcion_activa_por_alumno',
            ),
        ]


class Instalacion(models.Model):
    nombre = models.CharField(max_length=100)
    capacidad = models.IntegerField()
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'instalacion'


class Materia(models.Model):
    id_materia = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField()
    carga_horaria = models.IntegerField()
    cantidad_clases = models.IntegerField()

    class Meta:
        managed = True
        db_table = 'materia'


class Noticia(models.Model):
    id_noticia = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=200)
    contenido = models.TextField(max_length=350)
    fecha_publicacion = models.DateField()

    legajo_personal = models.ForeignKey(
        'PersonalAdministrativo',
        models.DO_NOTHING,
        db_column='legajo_personal'
    )

    imagen = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    class Meta:
        managed = True
        db_table = 'noticia'


class Persona(models.Model):
    id = models.AutoField(primary_key=True)
    id_usuario = models.ForeignKey(
        'Usuario', 
        models.DO_NOTHING, 
        db_column='id_usuario', 
        blank=True, 
        null=True)
    dni = models.CharField(unique=True, max_length=8)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    fecha_nacimiento = models.DateField()
    direccion = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, blank=True, null=True)
    email = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'persona'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"

class PersonalAdministrativo(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    sector = models.CharField(max_length=50)
    cargo = models.CharField(max_length=50)
    fecha_ingreso = models.DateField()

    class Meta:
        managed = True
        db_table = 'personal_administrativo'


class Preceptor(models.Model):
    legajo = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    turno = models.CharField(max_length=30, blank=True, null=True)
    fecha_ingreso = models.DateField()

    class Meta:
        managed = True
        db_table = 'preceptor'


class Reserva(models.Model):
    nombre = models.CharField(max_length=100)

    fecha = models.DateField()

    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()

    legajo_personal_evaluador = models.ForeignKey(
        PersonalAdministrativo,
        models.DO_NOTHING,
        db_column='legajo_personal_evaluador'
    )

    id_persona_solicitante = models.ForeignKey(
        Persona,
        models.DO_NOTHING,
        db_column='id_persona_solicitante'
    )

    id_instalacion = models.ForeignKey(
        Instalacion,
        models.DO_NOTHING,
        db_column='id_instalacion'
    )

    class Meta:
        managed = True
        db_table = 'reserva'


class SolicitudViaje(models.Model):
    id_solicitud = models.AutoField(primary_key=True)
    fecha_solicitud = models.DateField()
    estado = models.CharField(max_length=50)
    observaciones = models.TextField(blank=True, null=True)
    legajo_docente = models.ForeignKey(Docente, models.DO_NOTHING, db_column='legajo_docente')

    class Meta:
        managed = True
        db_table = 'solicitud_viaje'


class Tutor(models.Model):
    id = models.AutoField(primary_key=True)
    id_persona = models.ForeignKey(Persona, models.DO_NOTHING, db_column='id_persona')
    telefono_contacto = models.CharField(max_length=20, blank=True, null=True)
    email_contacto = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tutor'


class TutorTutoraAlumno(models.Model):
    id = models.AutoField(primary_key=True)

    id_tutor = models.ForeignKey(
        Tutor,
        models.DO_NOTHING,
        db_column='id_tutor'
    )

    id_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='id_alumno'
    )

    tipo_parentesco = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'tutor_tutora_alumno'


class Usuario(models.Model):
    id = models.AutoField(primary_key=True)
    nombre_usuario = models.CharField(unique=True, max_length=60)
    contrasenia = models.CharField(max_length=128)  # hash de Django (ver core/seguridad.py)
    correo = models.CharField(unique=True, max_length=100, blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'usuario'
        
    def __str__(self):
        return self.nombre_usuario


class Vehiculo(models.Model):
    id_vehiculo = models.AutoField(primary_key=True)
    patente = models.CharField(max_length=20)
    modelo = models.CharField(max_length=50)
    capacidad = models.IntegerField()
    estado = models.CharField(max_length=50)

    class Meta:
        managed = True
        db_table = 'vehiculo'


class Viaje(models.Model):
    id_viaje = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=50)
    fecha_salida = models.DateField()
    fecha_regreso = models.DateField()
    motivo = models.TextField()
    id_solicitud = models.OneToOneField(SolicitudViaje, models.DO_NOTHING, db_column='id_solicitud')

    class Meta:
        managed = True
        db_table = 'viaje'


class ViajeUtilizaVehiculo(models.Model):
    id_viaje = models.ForeignKey(Viaje, models.DO_NOTHING, db_column='id_viaje')
    id_vehiculo = models.ForeignKey(Vehiculo, models.DO_NOTHING, db_column='id_vehiculo')
    fecha_uso = models.DateField()

    class Meta:
        managed = True
        db_table = 'viaje_utiliza_vehiculo'

class PostulacionLaboral(models.Model):
    id = models.AutoField(primary_key=True)

    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)

    dni = models.CharField(max_length=15)

    correo = models.CharField(max_length=100)

    telefono = models.CharField(max_length=30)

    puesto = models.CharField(max_length=50)

    mensaje = models.TextField(
        blank=True,
        null=True
    )

    cv = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    fecha_postulacion = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'postulacion_laboral'

class SolicitudInscripcion(models.Model):
    id_solicitud = models.AutoField(primary_key=True)

    nombre_alumno = models.CharField(max_length=100)
    apellido_alumno = models.CharField(max_length=100)
    dni_alumno = models.CharField(max_length=8)

    fecha_nacimiento = models.DateField()

    nivel = models.CharField(max_length=30)
    turno = models.CharField(max_length=30)

    nombre_tutor = models.CharField(max_length=100)
    apellido_tutor = models.CharField(max_length=100)
    dni_tutor = models.CharField(max_length=8)

    telefono = models.CharField(max_length=20)
    email = models.CharField(max_length=100)

    direccion = models.CharField(max_length=100,blank=True,null=True)

    telefono_alumno = models.CharField(max_length=20,blank=True,null=True)

    email_alumno = models.CharField(max_length=100,blank=True,null=True)
    
    direccion_tutor = models.CharField(
        max_length=255,
        blank=True,
        default=""
    )


    observaciones = models.TextField(
        blank=True,
        null=True
    )

    fecha_solicitud = models.DateTimeField()

    estado = models.CharField(
        max_length=30,
        default='Pendiente'
    )

    parentesco = models.CharField(
        max_length=30,
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'solicitud_inscripcion'
        
class PagoPendiente(models.Model):
    id_pago = models.AutoField(primary_key=True)

    id_tutor = models.ForeignKey(
        Tutor,
        models.DO_NOTHING,
        db_column='id_tutor'
    )

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    mes = models.CharField(max_length=20)

    importe = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    estado = models.CharField(
        max_length=20,
        default='Pendiente'
    )

    fecha_solicitud = models.DateTimeField()

    class Meta:
        managed = True
        db_table = 'pago_pendiente'
        
class Arancel(models.Model):
    id_arancel = models.AutoField(primary_key=True)
    nivel = models.CharField(max_length=30)
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        managed = True
        db_table = 'arancel'
        
class ValorComedor(models.Model):
    """Valor mensual del servicio de comedor (único para todo el colegio)."""
    monto = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = 'valor_comedor'


class Factura(models.Model):
    """Factura mensual de un alumno, emitida a su tutor.

    El total se calcula en el backend a partir de los ítems; la app solo lo muestra.
    """
    ESTADOS = [("Pendiente", "Pendiente"), ("Parcial", "Parcial"), ("Pagada", "Pagada")]

    alumno = models.ForeignKey(Alumno, on_delete=models.PROTECT, related_name="facturas")
    tutor = models.ForeignKey(Tutor, on_delete=models.PROTECT, related_name="facturas")
    periodo = models.CharField(max_length=7, help_text="Formato AAAA-MM")
    emision = models.DateField()
    vencimiento = models.DateField()
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Pendiente")

    class Meta:
        db_table = "factura"
        ordering = ["-periodo"]
        constraints = [
            models.UniqueConstraint(fields=["alumno", "periodo"], name="uniq_factura_alumno_periodo"),
        ]

    def __str__(self):
        return f"Factura {self.periodo} - legajo {self.alumno_id}"


class ItemFactura(models.Model):
    """Concepto de una factura: cuota, deporte, transporte o comedor."""
    TIPOS = [("cuota", "Cuota"), ("deporte", "Deporte"), ("transporte", "Transporte"), ("comedor", "Comedor")]

    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="items")
    tipo = models.CharField(max_length=20, choices=TIPOS)
    descripcion = models.CharField(max_length=200)
    importe = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        db_table = "item_factura"


def ruta_comprobante(instance, filename):
    """Nombre aleatorio: el archivo original del tutor no se usa en disco."""
    import os
    import uuid
    extension = os.path.splitext(filename)[1].lower()
    return f"comprobantes/{instance.factura.periodo}/{uuid.uuid4().hex}{extension}"


class ComprobantePago(models.Model):
    """Comprobante de transferencia cargado por el tutor. Una factura puede tener varios."""
    ESTADOS = [("Pendiente", "Pendiente"), ("Aprobado", "Aprobado"), ("Rechazado", "Rechazado")]

    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="comprobantes")
    archivo = models.FileField(upload_to=ruta_comprobante)
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Pendiente")
    subido_por = models.ForeignKey(
        "Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="comprobantes_subidos"
    )

    class Meta:
        db_table = "comprobante_pago"
        ordering = ["-fecha_carga"]


class SolicitudPago(models.Model):
    """Pedido de pago de un tutor sobre ítems de una factura. El total lo calcula el servidor.

    La clave de idempotencia evita duplicados si la app reintenta la misma solicitud.
    Además, no puede haber dos solicitudes pendientes sobre la misma factura.
    """
    ESTADOS = [("Pendiente", "Pendiente"), ("Pagada", "Pagada"), ("Cancelada", "Cancelada")]

    factura = models.ForeignKey(Factura, on_delete=models.CASCADE, related_name="solicitudes_pago")
    items = models.ManyToManyField(ItemFactura, related_name="solicitudes_pago")
    total = models.DecimalField(max_digits=10, decimal_places=2)
    clave_idempotencia = models.CharField(max_length=64, unique=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default="Pendiente")
    creada_por = models.ForeignKey(
        "Usuario", on_delete=models.SET_NULL, null=True, blank=True, related_name="solicitudes_pago"
    )
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "solicitud_pago"
        ordering = ["-fecha"]
        constraints = [
            models.UniqueConstraint(
                fields=["factura"],
                condition=Q(estado="Pendiente"),
                name="uniq_solicitud_pendiente_por_factura",
            ),
        ]


class DocumentacionAlumno(models.Model):
    id_documentacion = models.AutoField(
        primary_key=True
    )

    legajo_alumno = models.ForeignKey(
        Alumno,
        models.DO_NOTHING,
        db_column='legajo_alumno'
    )

    dni_frente = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    dni_dorso = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    partida_nacimiento = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    certificado_salud = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    fecha_envio = models.DateTimeField()

    estado = models.CharField(
        max_length=20,
        default='Pendiente'
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )
    
    fecha_revision = models.DateTimeField(
        blank=True,
        null=True
    )

    id_administrativo = models.ForeignKey(
        PersonalAdministrativo,
        models.DO_NOTHING,
        db_column='id_administrativo',
        blank=True,
        null=True
    )

    class Meta:
        managed = True
        db_table = 'documentacion_alumno'
