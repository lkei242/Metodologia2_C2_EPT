from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from datetime import date

from .management_forms import (
    AlumnoGestionForm, CursoGestionForm, CursoMateriaGestionForm,
    DocenteCursoMateriaGestionForm, DocenteGestionForm,
    InscripcionCursoForm, MateriaGestionForm,
)
from .models import (
    Alumno, Curso, CursoCursaMaterias, Docente, DocenteCursoMateria,
    Inscripcion, Materia, Persona, InscripcionTransporte, RecorridoTransporte,
)
from .views import obtener_datos_sesion
from .domain_services import publicar_cambio


def _autorizar_gestion(request):
    persona, dashboard_url = obtener_datos_sesion(request)
    if not persona:
        return None, redirect(f"{reverse('login')}?next={request.path}")
    if dashboard_url != "dashboard-administrativo":
        return None, HttpResponseForbidden("Solo el personal administrativo puede gestionar estos datos.")
    return persona, None


def _form_context(request, form, titulo, descripcion=""):
    return render(request, "core/gestion_form.html", {
        "form": form, "titulo": titulo, "descripcion": descripcion,
    })


@require_http_methods(["GET"])
def gestion_inicio(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    return render(request, "core/gestion_inicio.html", {
        "alumnos": Alumno.objects.select_related("id_persona", "id_curso").order_by("id_persona__apellido", "id_persona__nombre"),
        "docentes": Docente.objects.select_related("id_persona").order_by("id_persona__apellido", "id_persona__nombre"),
        "cursos": Curso.objects.all().order_by("nivel", "anio", "comision"),
        "materias": Materia.objects.all().order_by("nombre"),
        "recorridos": RecorridoTransporte.objects.filter(activo=True),
    })


def _guardar_alumno(form, alumno=None, request=None):
    data = form.cleaned_data
    creating = alumno is None
    with transaction.atomic():
        if alumno:
            persona = alumno.id_persona
        else:
            persona = Persona()
        for field in ("dni", "nombre", "apellido", "fecha_nacimiento", "direccion", "telefono", "email"):
            setattr(persona, field, data[field])
        persona.save()
        if alumno is None:
            alumno = Alumno(id_persona=persona)
        old_course_id = alumno.id_curso_id
        alumno.id_curso = data["curso"]
        alumno.estado = data["estado"]
        alumno.inscripto_comedor = data["inscripto_comedor"]
        alumno.save()
        active = list(Inscripcion.objects.select_for_update().filter(legajo_alumno=alumno, estado="Activa"))
        if len(active) > 1:
            raise IntegrityError("El alumno tiene más de una inscripción activa; revise los datos antes de continuar.")
        route = data["recorrido"]
        active_routes = list(InscripcionTransporte.objects.select_for_update().filter(alumno=alumno, estado="Activa"))
        if len(active_routes) > 1:
            raise IntegrityError("El alumno tiene más de un recorrido activo; requiere revisión.")
        if active_routes and (route is None or active_routes[0].recorrido_id != route.pk):
            active_routes[0].estado = "Finalizada"
            active_routes[0].save(update_fields=["estado"])
        if route and (not active_routes or active_routes[0].recorrido_id != route.pk):
            InscripcionTransporte.objects.create(alumno=alumno, recorrido=route, estado="Activa")
        if not active:
            Inscripcion.objects.create(legajo_alumno=alumno, id_curso=data["curso"], estado="Activa", fecha_inscripcion=date.today())
        elif active[0].id_curso_id != data["curso"].pk or old_course_id != data["curso"].pk:
            active[0].estado = "Finalizada"
            active[0].save(update_fields=["estado"])
            Inscripcion.objects.create(legajo_alumno=alumno, id_curso=data["curso"], estado="Activa", fecha_inscripcion=date.today())
        if request:
            publicar_cambio(request, "Alumno", alumno.legajo, "crear" if creating else "actualizar", ["persona", "curso", "estado", "comedor", "transporte", "inscripción"])
    return alumno


@require_http_methods(["GET", "POST"])
def gestion_alumno_nuevo(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    form = AlumnoGestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            alumno = _guardar_alumno(form, request=request)
        except IntegrityError:
            form.add_error(None, "No se pudo guardar: hay una duplicación o inconsistencia en los datos.")
        else:
            messages.success(request, f"Alumno {alumno.legajo} creado correctamente.")
            return redirect("gestion-inicio")
    return _form_context(request, form, "Alta de alumno", "El legajo se genera automáticamente y es único.")


@require_http_methods(["GET", "POST"])
def gestion_alumno_editar(request, legajo):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    alumno = get_object_or_404(Alumno.objects.select_related("id_persona", "id_curso"), pk=legajo)
    form = AlumnoGestionForm(request.POST or None, alumno=alumno)
    if request.method == "POST" and form.is_valid():
        try:
            _guardar_alumno(form, alumno, request=request)
        except IntegrityError:
            form.add_error(None, "No se pudo guardar: hay una duplicación o inconsistencia en los datos.")
        else:
            messages.success(request, "Ficha de alumno actualizada.")
            return redirect("gestion-inicio")
    return _form_context(request, form, f"Editar alumno {alumno.legajo}", "Los cambios se validan y guardan dentro de una transacción.")


def _guardar_docente(form, docente=None, request=None):
    data = form.cleaned_data
    creating = docente is None
    with transaction.atomic():
        persona = docente.id_persona if docente else Persona()
        for field in ("dni", "nombre", "apellido", "fecha_nacimiento", "direccion", "telefono", "email"):
            setattr(persona, field, data[field])
        persona.save()
        if docente is None:
            docente = Docente(id_persona=persona)
        docente.titulo = data["titulo"]
        docente.especialidad = data["especialidad"]
        docente.estado = data["estado"]
        if not docente.fecha_ingreso:
            from datetime import date
            docente.fecha_ingreso = date.today()
        docente.save()
        if request:
            publicar_cambio(request, "Docente", docente.legajo, "crear" if creating else "actualizar", ["persona", "título", "especialidad", "estado"])
    return docente


@require_http_methods(["GET", "POST"])
def gestion_docente_nuevo(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    form = DocenteGestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            docente = _guardar_docente(form, request=request)
        except IntegrityError:
            form.add_error(None, "No se pudo guardar: el DNI ya está utilizado.")
        else:
            messages.success(request, f"Docente {docente.legajo} creado correctamente.")
            return redirect("gestion-inicio")
    return _form_context(request, form, "Alta de docente", "El legajo se genera automáticamente y es único.")


@require_http_methods(["GET", "POST"])
def gestion_docente_editar(request, legajo):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    docente = get_object_or_404(Docente.objects.select_related("id_persona"), pk=legajo)
    form = DocenteGestionForm(request.POST or None, docente=docente)
    if request.method == "POST" and form.is_valid():
        try:
            _guardar_docente(form, docente, request=request)
        except IntegrityError:
            form.add_error(None, "No se pudo guardar: el DNI ya está utilizado.")
        else:
            messages.success(request, "Ficha docente actualizada.")
            return redirect("gestion-inicio")
    return _form_context(request, form, f"Editar docente {docente.legajo}")


@require_http_methods(["GET", "POST"])
def gestion_academica(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    forms = {
        "curso_form": CursoGestionForm(prefix="curso"),
        "materia_form": MateriaGestionForm(prefix="materia"),
        "relacion_form": CursoMateriaGestionForm(prefix="relacion"),
        "asignacion_form": DocenteCursoMateriaGestionForm(prefix="asignacion"),
    }
    if request.method == "POST":
        action = request.POST.get("action")
        form_types = {
            "curso": ("curso_form", CursoGestionForm),
            "materia": ("materia_form", MateriaGestionForm),
            "relacion": ("relacion_form", CursoMateriaGestionForm),
            "asignacion": ("asignacion_form", DocenteCursoMateriaGestionForm),
        }
        if action in form_types:
            key, form_type = form_types[action]
            form = form_type(request.POST, prefix=action)
            forms[key] = form
            if form.is_valid():
                try:
                    obj = form.save()
                    publicar_cambio(request, obj.__class__.__name__, obj.pk, "guardar", [field for field in form.cleaned_data])
                except IntegrityError:
                    form.add_error(None, "El registro duplicaría una relación existente.")
                else:
                    messages.success(request, "Configuración guardada correctamente.")
                    return redirect("gestion-academica")
    return render(request, "core/gestion_academica.html", {
        **forms,
        "cursos": Curso.objects.all().order_by("nivel", "anio", "comision"),
        "materias": Materia.objects.all().order_by("nombre"),
        "relaciones": CursoCursaMaterias.objects.select_related("id_curso", "id_materia").all(),
        "asignaciones": DocenteCursoMateria.objects.select_related("docente__id_persona", "curso", "materia").all(),
    })


@require_http_methods(["GET", "POST"])
def gestion_inscripcion(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    form = InscripcionCursoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            with transaction.atomic():
                alumno = Alumno.objects.select_for_update().get(pk=data["legajo_alumno"].pk)
                active = list(Inscripcion.objects.select_for_update().filter(legajo_alumno=alumno, estado="Activa"))
                if len(active) > 1:
                    raise IntegrityError("El alumno tiene inscripciones activas duplicadas.")
                if active:
                    if active[0].id_curso_id == data["id_curso"].pk:
                        raise IntegrityError("El alumno ya está inscripto activamente en ese curso.")
                    active[0].estado = "Finalizada"
                    active[0].save(update_fields=["estado"])
                alumno.id_curso = data["id_curso"]
                alumno.save(update_fields=["id_curso"])
                Inscripcion.objects.create(legajo_alumno=alumno, id_curso=data["id_curso"], estado="Activa", fecha_inscripcion=date.today())
                publicar_cambio(request, "Inscripcion", alumno.legajo, "inscribir", ["curso", "estado"])
        except IntegrityError as exc:
            form.add_error(None, str(exc) or "No se pudo registrar la inscripción activa.")
        else:
            messages.success(request, "Inscripción registrada; la anterior queda en el historial si hubo cambio.")
            return redirect("gestion-inicio")
    return _form_context(request, form, "Inscripción a cursado", "Al cambiar de curso se finaliza la inscripción anterior y se conserva el historial.")
