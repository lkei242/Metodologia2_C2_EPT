import re
from datetime import datetime, date
from django import forms
from .models import SolicitudInscripcion

_NOMBRE_REGEX = re.compile(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$')
_DNI_REGEX = re.compile(r'^\d{7,8}$')
_TELEFONO_REGEX = re.compile(r'^\d{8,15}$')
_RANGOS_NIVEL = {
    'inicial': (3, 5, 'Inicial'),
    'primario': (6, 11, 'Primario'),
    'secundario': (12, 18, 'Secundario'),
}


def calcular_edad(fecha_nacimiento):
    """Calcula la edad exacta en años dada una fecha de nacimiento."""
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year
    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1
    return edad


class InscripcionForm(forms.ModelForm):
    """Formulario para la solicitud de inscripción de un estudiante.
    
    Gestiona la validación de nombres, documentos, números telefónicos
    y coherencia de edad según el nivel académico seleccionado.
    """

    nombre = forms.CharField(max_length=100)
    apellido = forms.CharField(max_length=100)
    dni = forms.CharField(max_length=8)
    fecha = forms.CharField(required=False)
    direccion = forms.CharField(max_length=100)
    telefono_alumno = forms.CharField(required=False)
    email_alumno = forms.EmailField(required=False)
    nivel = forms.CharField(max_length=30)
    turno = forms.CharField(max_length=30)
    tutor = forms.CharField(max_length=100)
    apellido_tutor = forms.CharField(max_length=100)
    dni_tutor = forms.CharField(max_length=8)
    parentesco = forms.CharField(required=False)
    telefono = forms.CharField(max_length=20)
    email = forms.EmailField(required=False)
    direccion_tutor = forms.CharField(required=False)
    observaciones = forms.CharField(required=False, widget=forms.Textarea)

    class Meta:
        model = SolicitudInscripcion
        fields = [
            'nivel', 'turno', 'parentesco', 'telefono', 'email',
            'direccion_tutor', 'observaciones'
        ]

    def clean(self):
        cleaned_data = super().clean()
        
        # Validar nombres de alumno y tutor
        campos_nombre = (
            ('nombre', 'El nombre'),
            ('apellido', 'El apellido'),
            ('tutor', 'El nombre del tutor'),
            ('apellido_tutor', 'El apellido del tutor'),
        )
        for campo, etiqueta in campos_nombre:
            valor = (cleaned_data.get(campo) or '').strip()
            if not valor:
                self.add_error(campo, f'{etiqueta} es obligatorio.')
            elif not _NOMBRE_REGEX.match(valor):
                self.add_error(campo, f'{etiqueta} solo puede contener letras.')

        # Validar DNIs
        for campo, etiqueta in (('dni', 'El DNI'), ('dni_tutor', 'El DNI del tutor')):
            valor = (cleaned_data.get(campo) or '').strip()
            if not _DNI_REGEX.match(valor):
                self.add_error(campo, f'{etiqueta} debe tener 7 u 8 dígitos numéricos.')

        # Validar dirección
        direccion = (cleaned_data.get('direccion') or '').strip()
        if not direccion:
            self.add_error('direccion', 'La dirección del estudiante es obligatoria.')

        # Validar teléfonos
        telefono = (cleaned_data.get('telefono') or '').strip()
        if not _TELEFONO_REGEX.match(telefono):
            self.add_error('telefono', 'El teléfono debe contener solo números (entre 8 y 15 dígitos).')

        telefono_alumno = (cleaned_data.get('telefono_alumno') or '').strip()
        if telefono_alumno and not _TELEFONO_REGEX.match(telefono_alumno):
            self.add_error('telefono_alumno', 'El teléfono del alumno debe contener solo números (entre 8 y 15 dígitos).')

        # Validar coincidencia de edad con el nivel seleccionado
        nivel = cleaned_data.get('nivel')
        fecha_str = cleaned_data.get('fecha')
        if fecha_str and nivel in _RANGOS_NIVEL:
            try:
                fecha_nac = datetime.strptime(fecha_str, '%Y-%m-%d').date()
                edad = calcular_edad(fecha_nac)
                min_edad, max_edad, label = _RANGOS_NIVEL[nivel]
                if edad < min_edad or edad > max_edad:
                    self.add_error(
                        'fecha',
                        f'La edad ({edad} años) no corresponde al Nivel {label} (de {min_edad} a {max_edad} años).'
                    )
            except ValueError:
                self.add_error('fecha', 'La fecha de nacimiento no es válida.')

        return cleaned_data

    def guardar_solicitud(self):
        """Crea la instancia de SolicitudInscripcion mapeando los campos recibidos."""
        from django.utils import timezone
        cd = self.cleaned_data
        return SolicitudInscripcion.objects.create(
            nombre_alumno=cd.get('nombre'),
            apellido_alumno=cd.get('apellido'),
            dni_alumno=cd.get('dni'),
            fecha_nacimiento=cd.get('fecha'),
            direccion=cd.get('direccion'),
            telefono_alumno=cd.get('telefono_alumno'),
            email_alumno=cd.get('email_alumno'),
            nivel=cd.get('nivel'),
            turno=cd.get('turno'),
            nombre_tutor=cd.get('tutor'),
            apellido_tutor=cd.get('apellido_tutor'),
            dni_tutor=cd.get('dni_tutor'),
            parentesco=cd.get('parentesco'),
            telefono=cd.get('telefono'),
            email=cd.get('email'),
            direccion_tutor=cd.get('direccion_tutor'),
            observaciones=cd.get('observaciones'),
            fecha_solicitud=timezone.now(),
            estado='Pendiente'
        )
