from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .business_forms import GrupoDeportivoForm, InscripcionDeportivaForm, RecorridoTransporteForm
from .domain_services import ReglaNegocioError, asignar_transporte, inscribir_en_deporte
from .domain_services import publicar_cambio, finalizar_deporte
from .management_views import _autorizar_gestion
from .models import (Alumno, Arancel, DisciplinaDeportiva, GrupoDeportivo,
                     InscripcionDeportiva, InscripcionTransporte,
                     RecorridoTransporte, Tutor, TutorTutoraAlumno,
                     ValorComedor)
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


@require_http_methods(["GET", "POST"])
def gestion_valores(request):
    """Pantalla administrativa para fijar los importes de cuotas y servicios (G1 / RF-M15)."""
    _, denied = _autorizar_gestion(request)
    if denied:
        return denied

    niveles = ["Inicial", "Primario", "Secundario"]
    for niv, monto_defecto in [("Inicial", 48000.00), ("Primario", 25000.00), ("Secundario", 32000.00)]:
        Arancel.objects.get_or_create(nivel=niv, defaults={"monto": monto_defecto})

    # La facturación lee la cuota de Arancel (por nivel), el comedor de ValorComedor,
    # el deporte de DisciplinaDeportiva.valor y el transporte de RecorridoTransporte.valor.
    # Esta pantalla edita exactamente esas fuentes, sin tablas espejo.
    aranceles = list(Arancel.objects.filter(nivel__in=niveles).order_by("nivel"))
    valor_comedor = ValorComedor.objects.first()
    disciplinas = list(DisciplinaDeportiva.objects.order_by("nombre"))
    recorridos = list(RecorridoTransporte.objects.order_by("nombre"))

    if request.method == "POST":
        errores = []
        cambios = []  # (entidad, objeto, campo, nuevo valor, etiqueta)

        def evaluar(entidad, objeto, campo, nombre_campo, etiqueta):
            crudo = request.POST.get(nombre_campo)
            if crudo is None:
                return
            try:
                nuevo = _leer_importe(crudo)
            except ValueError as exc:
                errores.append(f"{etiqueta}: {exc}.")
                return
            if nuevo is not None and getattr(objeto, campo, None) != nuevo:
                cambios.append((entidad, objeto, campo, nuevo, etiqueta))

        for arancel in aranceles:
            evaluar("Arancel", arancel, "monto", f"monto_{arancel.pk}", f"Cuota {arancel.nivel}")
        for disciplina in disciplinas:
            evaluar("DisciplinaDeportiva", disciplina, "valor", f"disc_{disciplina.pk}", f"Deporte {disciplina.nombre}")
        for recorrido in recorridos:
            evaluar("RecorridoTransporte", recorrido, "valor", f"rec_{recorrido.pk}", recorrido.nombre)
        if valor_comedor is not None:
            evaluar("ValorComedor", valor_comedor, "monto", "comedor", "Comedor")
        else:
            try:
                nuevo_comedor = _leer_importe(request.POST.get("comedor"))
            except ValueError as exc:
                errores.append(f"Comedor: {exc}.")
            else:
                if nuevo_comedor is not None:
                    cambios.append(("ValorComedor", None, "monto", nuevo_comedor, "Comedor"))

        if errores:
            for error in errores:
                messages.error(request, error)
            return redirect("gestion-valores")

        if not cambios:
            messages.info(request, "No se registraron cambios en los importes.")
            return redirect("gestion-valores")

        modificados_por_entidad = {}
        with transaction.atomic():
            for entidad, objeto, campo, nuevo, etiqueta in cambios:
                if objeto is None:
                    objeto = ValorComedor.objects.create(monto=nuevo)
                else:
                    setattr(objeto, campo, nuevo)
                    objeto.save(update_fields=[campo])
                modificados_por_entidad.setdefault(entidad, []).append(etiqueta)
            for entidad, etiquetas in modificados_por_entidad.items():
                publicar_cambio(request, entidad, "lote", "actualizar", etiquetas)
        modificados = [etiqueta for etiquetas in modificados_por_entidad.values() for etiqueta in etiquetas]
        messages.success(request, f"Valores actualizados para: {', '.join(modificados)}.")
        return redirect("gestion-valores")

    return render(request, "core/gestion_valores.html", {
        "aranceles_cuotas": aranceles,
        "valor_comedor": valor_comedor,
        "disciplinas": disciplinas,
        "recorridos": recorridos,
    })


def _leer_importe(crudo):
    """Convierte el texto del formulario en un importe válido.

    Devuelve None si el campo vino vacío (no se modifica) y lanza ValueError con un
    mensaje legible si el valor no es un importe permitido.
    """
    texto = (crudo or "").strip().replace(",", ".")
    if texto == "":
        return None
    try:
        valor = Decimal(texto)
    except InvalidOperation:
        raise ValueError("no es un número válido")
    if not valor.is_finite() or valor < 0:
        raise ValueError("debe ser un número mayor o igual a cero")
    if valor >= Decimal("100000000"):
        raise ValueError("el importe es demasiado grande")
    return valor.quantize(Decimal("0.01"))
