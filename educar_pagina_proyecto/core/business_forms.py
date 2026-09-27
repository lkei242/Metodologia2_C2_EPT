from django import forms

from .models import GrupoDeportivo, InscripcionDeportiva, RecorridoTransporte
from .patterns import ConfiguracionTecnicaSingleton


class RecorridoTransporteForm(forms.ModelForm):
    class Meta:
        model = RecorridoTransporte
        fields = ["nombre", "descripcion", "activo"]
        labels = {"nombre": "Nombre del recorrido", "descripcion": "Descripción", "activo": "Activo"}

    def clean(self):
        data = super().clean()
        maximo = ConfiguracionTecnicaSingleton().get("max_recorridos_transporte")
        if not self.instance.pk and RecorridoTransporte.objects.count() >= maximo:
            raise forms.ValidationError("La institución tiene un máximo de cuatro recorridos configurados.")
        return data


class GrupoDeportivoForm(forms.ModelForm):
    class Meta:
        model = GrupoDeportivo
        fields = ["disciplina", "nivel", "dia_semana", "hora_inicio", "hora_fin", "profesor_responsable"]
        widgets = {"hora_inicio": forms.TimeInput(attrs={"type": "time"}), "hora_fin": forms.TimeInput(attrs={"type": "time"})}
        labels = {"disciplina": "Deporte", "nivel": "Nivel", "dia_semana": "Día", "hora_inicio": "Hora de inicio", "hora_fin": "Hora de fin", "profesor_responsable": "Profesor responsable"}


class InscripcionDeportivaForm(forms.ModelForm):
    class Meta:
        model = InscripcionDeportiva
        fields = ["alumno", "grupo"]
        labels = {"alumno": "Alumno", "grupo": "Grupo deportivo"}
