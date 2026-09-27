from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .business_forms import GrupoDeportivoForm, InscripcionDeportivaForm, RecorridoTransporteForm
from .domain_services import ReglaNegocioError, asignar_transporte, inscribir_en_deporte
from .domain_services import publicar_cambio, finalizar_deporte
from .management_views import _autorizar_gestion
from .models import (Alumno, GrupoDeportivo, InscripcionDeportiva,
                     InscripcionTransporte, RecorridoTransporte,
                     Tutor, TutorTutoraAlumno)
from .views import obtener_datos_sesion


@require_http_methods(["GET", "POST"])
def gestion_servicios(request):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    route_form = RecorridoTransporteForm(prefix="recorrido")
    group_form = GrupoDeportivoForm(prefix="grupo")
    sport_form = InscripcionDeportivaForm(prefix="deporte")
    if request.method == "POST":
        action = request.POST.get("action")
        form_class = {"recorrido": RecorridoTransporteForm, "grupo": GrupoDeportivoForm, "deporte": InscripcionDeportivaForm}.get(action)
        if form_class:
            form = form_class(request.POST, prefix=action)
            if action == "recorrido": route_form = form
            elif action == "grupo": group_form = form
            else: sport_form = form
            if form.is_valid():
                try:
                    if action == "deporte":
                        row = inscribir_en_deporte(
                            form.cleaned_data["alumno"].pk,
                            form.cleaned_data["grupo"].pk,
                            confirmar_migracion=request.POST.get("confirmar_migracion") == "on",
                        )
                        publicar_cambio(request, "InscripcionDeportiva", row.pk, "inscribir", ["alumno", "grupo", "estado"])
                    else:
                        row = form.save()
                        publicar_cambio(request, row.__class__.__name__, row.pk, "crear", list(form.cleaned_data))
                except (IntegrityError, ReglaNegocioError) as exc:
                    form.add_error(None, str(exc) or "La operación entra en conflicto con una regla de negocio.")
                else:
                    messages.success(request, "Cambio guardado correctamente.")
                    return redirect("gestion-servicios")
    return render(request, "core/gestion_servicios.html", {
        "recorrido_form": route_form,
        "grupo_form": group_form,
        "deporte_form": sport_form,
        "recorridos": RecorridoTransporte.objects.all(),
        "grupos": GrupoDeportivo.objects.select_related("disciplina", "profesor_responsable__id_persona").all(),
        "inscripciones": InscripcionDeportiva.objects.filter(estado="Activa").select_related("alumno__id_persona", "grupo__disciplina"),
        "cantidad_recorridos": RecorridoTransporte.objects.count(),
    })


@require_http_methods(["POST"])
def finalizar_inscripcion_deportiva(request, inscripcion_id):
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied
    try:
        row = finalizar_deporte(inscripcion_id=inscripcion_id, alumno_id=InscripcionDeportiva.objects.get(pk=inscripcion_id).alumno_id)
        publicar_cambio(request, "InscripcionDeportiva", row.pk, "finalizar", ["estado"])
    except InscripcionDeportiva.DoesNotExist:
        messages.error(request, "La inscripción deportiva ya no está activa.")
    else:
        messages.success(request, "Inscripción deportiva finalizada.")
    return redirect("gestion-servicios")


@require_http_methods(["GET", "POST"])
def familia_servicios(request):
    persona, role = obtener_datos_sesion(request)
    if not persona:
        return redirect("login")
    if role != "dashboard-padres":
        return HttpResponseForbidden("Este espacio es exclusivo para tutores.")
    tutor = Tutor.objects.filter(id_persona=persona).first()
    alumnos = Alumno.objects.filter(tutortutoraalumno__id_tutor=tutor).distinct() if tutor else Alumno.objects.none()
    if request.method == "POST":
        alumno = alumnos.filter(pk=request.POST.get("alumno")).first()
        if not alumno:
            return HttpResponseForbidden("Solo puede gestionar hijos vinculados a su cuenta.")
        action = request.POST.get("action")
        try:
            if action == "deporte":
                group = GrupoDeportivo.objects.get(pk=request.POST.get("grupo"))
                row = inscribir_en_deporte(alumno.pk, group.pk)
                publicar_cambio(request, "InscripcionDeportiva", row.pk, "inscribir", ["alumno", "grupo", "estado"])
            elif action == "transporte":
                raw_route = request.POST.get("recorrido") or None
                route = RecorridoTransporte.objects.filter(pk=raw_route, activo=True).first() if raw_route else None
                if raw_route and not route:
                    raise ReglaNegocioError("Seleccione un recorrido activo válido.")
                row = asignar_transporte(alumno.pk, route.pk if route else None)
                publicar_cambio(request, "InscripcionTransporte", row.pk if row else alumno.pk, "asignar" if row else "retirar", ["alumno", "recorrido"])
            elif action == "finalizar":
                row = InscripcionDeportiva.objects.get(pk=request.POST.get("inscripcion"), alumno=alumno, estado="Activa")
                row = finalizar_deporte(alumno.pk, row.pk)
                publicar_cambio(request, "InscripcionDeportiva", row.pk, "finalizar", ["estado"])
            else:
                raise ReglaNegocioError("Acción inválida.")
        except (InscripcionDeportiva.DoesNotExist, GrupoDeportivo.DoesNotExist, ReglaNegocioError, IntegrityError) as exc:
            messages.error(request, str(exc) or "No se pudo guardar el cambio.")
        else:
            messages.success(request, "Cambio guardado correctamente.")
        return redirect("familia-servicios")
    return render(request, "core/familia_servicios.html", {
        "hijos": alumnos.select_related("id_persona", "id_curso").prefetch_related("inscripciones_deportivas__grupo__disciplina", "inscripciones_transporte__recorrido"),
        "grupos": GrupoDeportivo.objects.select_related("disciplina", "profesor_responsable__id_persona").all(),
        "recorridos": RecorridoTransporte.objects.filter(activo=True),
    })
