from django import forms
from django.core.validators import RegexValidator
from django.db.models import Q

from .models import (
    Alumno, Curso, CursoCursaMaterias, Docente, DocenteCursoMateria,
    Inscripcion, Materia, Persona, RecorridoTransporte, InscripcionTransporte,
)

DNI_VALIDATOR = RegexValidator(r"^\d{7,8}$", "El DNI debe tener 7 u 8 dígitos.")


class AlumnoGestionForm(forms.Form):
    dni = forms.CharField(max_length=8, validators=[DNI_VALIDATOR])
    nombre = forms.CharField(max_length=50)
    apellido = forms.CharField(max_length=50)
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    direccion = forms.CharField(max_length=100, required=False)
    telefono = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(max_length=100, required=False, label="Correo electrónico")
    curso = forms.ModelChoiceField(queryset=Curso.objects.none(), label="Curso")
    estado = forms.ChoiceField(choices=Alumno.ESTADOS)
    inscripto_comedor = forms.BooleanField(required=False, label="Inscripto al comedor")
    recorrido = forms.ModelChoiceField(queryset=RecorridoTransporte.objects.none(), required=False, label="Recorrido de transporte")

    def __init__(self, *args, alumno=None, **kwargs):
        self.alumno = alumno
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = Curso.objects.all().order_by("nivel", "anio", "comision")
        self.fields["recorrido"].queryset = RecorridoTransporte.objects.filter(activo=True).order_by("nombre")
        if alumno and not kwargs.get("initial"):
            p = alumno.id_persona
            self.initial.update({
                "dni": p.dni, "nombre": p.nombre, "apellido": p.apellido,
                "fecha_nacimiento": p.fecha_nacimiento, "direccion": p.direccion,
                "telefono": p.telefono, "email": p.email,
                "curso": alumno.id_curso_id, "estado": alumno.estado,
                "inscripto_comedor": alumno.inscripto_comedor,
                "recorrido": alumno.inscripciones_transporte.filter(estado="Activa").values_list("recorrido_id", flat=True).first(),
            })

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        people = Persona.objects.filter(dni=dni)
        if self.alumno:
            people = people.exclude(pk=self.alumno.id_persona_id)
        if people.exists():
            raise forms.ValidationError("Ya existe una persona con ese DNI.")
        return dni

    def clean(self):
        data = super().clean()
        if data.get("curso") and self.alumno and self.alumno.id_curso_id != data["curso"].pk:
            active = Inscripcion.objects.filter(legajo_alumno=self.alumno, estado="Activa")
            if active.count() > 1:
                self.add_error("curso", "El alumno tiene más de una inscripción activa; requiere revisión administrativa.")
        return data


class DocenteGestionForm(forms.Form):
    dni = forms.CharField(max_length=8, validators=[DNI_VALIDATOR])
    nombre = forms.CharField(max_length=50)
    apellido = forms.CharField(max_length=50)
    fecha_nacimiento = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    direccion = forms.CharField(max_length=100, required=False)
    telefono = forms.CharField(max_length=20, required=False)
    email = forms.EmailField(max_length=100, required=False, label="Correo electrónico")
    titulo = forms.CharField(max_length=100, label="Título")
    especialidad = forms.CharField(max_length=100, required=False)
    estado = forms.ChoiceField(choices=Docente.ESTADOS)

    def __init__(self, *args, docente=None, **kwargs):
        self.docente = docente
        super().__init__(*args, **kwargs)
        if docente and not kwargs.get("initial"):
            p = docente.id_persona
            self.initial.update({
                "dni": p.dni, "nombre": p.nombre, "apellido": p.apellido,
                "fecha_nacimiento": p.fecha_nacimiento, "direccion": p.direccion,
                "telefono": p.telefono, "email": p.email,
                "titulo": docente.titulo, "especialidad": docente.especialidad,
                "estado": docente.estado,
            })

    def clean_dni(self):
        dni = self.cleaned_data["dni"].strip()
        people = Persona.objects.filter(dni=dni)
        if self.docente:
            people = people.exclude(pk=self.docente.id_persona_id)
        if people.exists():
            raise forms.ValidationError("Ya existe una persona con ese DNI.")
        return dni


class CursoGestionForm(forms.ModelForm):
    class Meta:
        model = Curso
        fields = ["nivel", "anio", "comision", "turno", "cupo_maximo", "legajo_preceptor", "id_aula"]
        labels = {"anio": "Año del curso", "comision": "Comisión", "turno": "Turno", "cupo_maximo": "Cupo máximo", "legajo_preceptor": "Preceptor", "id_aula": "Aula"}

    def clean(self):
        data = super().clean()
        if data.get("anio", 0) <= 0:
            self.add_error("anio", "El año del curso debe ser mayor que cero.")
        return data


class MateriaGestionForm(forms.ModelForm):
    class Meta:
        model = Materia
        fields = ["nombre", "descripcion", "carga_horaria", "cantidad_clases"]
        labels = {"nombre": "Materia", "descripcion": "Descripción", "carga_horaria": "Carga horaria", "cantidad_clases": "Cantidad de clases"}


class CursoMateriaGestionForm(forms.ModelForm):
    class Meta:
        model = CursoCursaMaterias
        fields = ["id_curso", "id_materia", "horarios"]
        labels = {"id_curso": "Curso", "id_materia": "Materia", "horarios": "Horarios"}

    def clean(self):
        data = super().clean()
        if data.get("id_curso") and data.get("id_materia"):
            duplicates = CursoCursaMaterias.objects.filter(id_curso=data["id_curso"], id_materia=data["id_materia"])
            if self.instance and self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                raise forms.ValidationError("La materia ya está asociada a ese curso.")
        return data


class DocenteCursoMateriaGestionForm(forms.ModelForm):
    class Meta:
        model = DocenteCursoMateria
        fields = ["docente", "curso", "materia"]

    def clean(self):
        data = super().clean()
        if data.get("curso") and data.get("materia") and not CursoCursaMaterias.objects.filter(id_curso=data["curso"], id_materia=data["materia"]).exists():
            self.add_error("materia", "Primero asocie la materia al curso.")
        return data


class InscripcionCursoForm(forms.Form):
    legajo_alumno = forms.ModelChoiceField(queryset=Alumno.objects.none(), label="Alumno")
    id_curso = forms.ModelChoiceField(queryset=Curso.objects.none(), label="Curso")
    cambiar_curso = forms.BooleanField(required=False, label="Confirmo el cambio de curso y conservar el historial")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["legajo_alumno"].queryset = Alumno.objects.select_related("id_persona").order_by("id_persona__apellido", "id_persona__nombre")
        self.fields["id_curso"].queryset = Curso.objects.all().order_by("nivel", "anio", "comision")

    def clean(self):
        data = super().clean()
        alumno, curso = data.get("legajo_alumno"), data.get("id_curso")
        if alumno and curso:
            active = Inscripcion.objects.filter(legajo_alumno=alumno, estado="Activa")
            if active.count() > 1:
                self.add_error("legajo_alumno", "El alumno ya tiene inscripciones activas duplicadas; se requiere revisión.")
            elif active.exists() and active.first().id_curso_id == curso.pk:
                self.add_error("id_curso", "El alumno ya está inscripto activamente en ese curso.")
            elif active.exists() and not data.get("cambiar_curso"):
                self.add_error("cambiar_curso", "Marque la confirmación para finalizar la inscripción anterior y cambiar de curso.")
        return data
