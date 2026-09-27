from collections import defaultdict

from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from .models import (
    Alumno, AuditoriaCambio, Curso, CursoCursaMaterias, DisciplinaDeportiva,
    Docente, DocenteCursoMateria, InscripcionDeportiva, InscripcionTransporte,
    GrupoDeportivo, Materia, RecorridoTransporte, Tutor,
)
from .patterns import ConfiguracionTecnicaSingleton, DjangoReportesAdapter
from .views import obtener_datos_sesion


REPORTS = {
    "R-01": "Por alumno",
    "R-02": "Por docente",
    "R-03": "Alumnos por curso",
    "R-04": "Alumnos por materia",
    "R-05": "Docentes por nivel",
    "R-06": "Alumnos por deporte",
    "R-07": "Deporte por nivel y horario",
    "R-08": "Alumnos por recorrido",
}


def _authorized(request):
    persona, role = obtener_datos_sesion(request)
    if not persona:
        return None, redirect("login")
    if role not in {"dashboard-administrativo", "dashboard-directivo"}:
        return None, HttpResponseForbidden("Los reportes institucionales están reservados a Administración y Dirección.")
    return persona, None


def _text(instance):
    return f"{instance.id_persona.apellido}, {instance.id_persona.nombre}"


def _row(headers, *values):
    return {key: value if value not in (None, "") else "—" for key, value in zip(headers, values)}


def _filters(request):
    return {
        "alumno": request.GET.get("alumno", ""),
        "docente": request.GET.get("docente", ""),
        "curso": request.GET.get("curso", ""),
        "materia": request.GET.get("materia", ""),
        "nivel": request.GET.get("nivel", ""),
        "deporte": request.GET.get("deporte", ""),
        "recorrido": request.GET.get("recorrido", ""),
    }


def _valid_id(value, model):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if model.objects.filter(pk=parsed).exists() else None


def build_report(code, filters):
    adapter = DjangoReportesAdapter()
    alumnos = adapter.alumnos()
    assignments = adapter.asignaciones_docentes()
    active_sports = adapter.inscripciones_deportivas()
    active_transport = adapter.inscripciones_transporte()

    course_id = _valid_id(filters.get("curso"), Curso)
    student_id = _valid_id(filters.get("alumno"), Alumno)
    teacher_id = _valid_id(filters.get("docente"), Docente)
    subject_id = _valid_id(filters.get("materia"), Materia)
    sport_id = _valid_id(filters.get("deporte"), DisciplinaDeportiva)
    route_id = _valid_id(filters.get("recorrido"), RecorridoTransporte)
    level = filters.get("nivel")

    if student_id:
        alumnos = alumnos.filter(pk=student_id)
    if course_id:
        alumnos = alumnos.filter(id_curso_id=course_id)
    if level:
        alumnos = alumnos.filter(id_curso__nivel__iexact=level)

    if code == "R-01":
        headers = ["Alumno", "Curso", "Materias y docentes", "Deportes y horarios", "Transporte", "Comedor"]
        rows = []
        for alumno in alumnos:
            relations = CursoCursaMaterias.objects.filter(id_curso=alumno.id_curso)
            if subject_id:
                relations = relations.filter(id_materia_id=subject_id)
            subjects = []
            for relation in relations.select_related("id_materia"):
                names = list(assignments.filter(curso=alumno.id_curso, materia=relation.id_materia).values_list("docente__id_persona__apellido", "docente__id_persona__nombre"))
                if not names:
                    from .models import DocenteDictaMateria
                    teacher_names = list(DocenteDictaMateria.objects.filter(id_materia=relation.id_materia).values_list("id_docente__id_persona__apellido", "id_docente__id_persona__nombre").distinct())
                    names = teacher_names if len(teacher_names) == 1 else []
                teacher_text = ", ".join(f"{last}, {first}" for last, first in names) or "Asignación docente por curso pendiente"
                subjects.append(f"{relation.id_materia.nombre} ({teacher_text})")
            sports = []
            for enrollment in active_sports.filter(alumno=alumno):
                if sport_id and enrollment.grupo.disciplina_id != sport_id:
                    continue
                sports.append(f"{enrollment.grupo.disciplina.nombre}: {enrollment.grupo.dia_semana} {enrollment.grupo.hora_inicio:%H:%M}-{enrollment.grupo.hora_fin:%H:%M}")
            if alumno.id_disciplina_id and (not sport_id or alumno.id_disciplina_id == sport_id):
                sports.append(f"{alumno.id_disciplina.nombre}: horario legado sin estructura de grupo")
            route = active_transport.filter(alumno=alumno).first()
            rows.append(_row(headers, _text(alumno), f"{alumno.id_curso.nivel} {alumno.id_curso.anio}° {alumno.id_curso.comision}" if alumno.id_curso else "Sin curso", "; ".join(subjects), "; ".join(sports), route.recorrido.nombre if route else "No utiliza", "Sí" if alumno.inscripto_comedor else "No"))
        return headers, rows, "R-01 agrega datos por alumno; una asignación docente ambigua se identifica como pendiente en vez de inferirla."

    if code == "R-02":
        headers = ["Docente", "Nivel", "Curso", "Horario del curso"]
        qs = assignments
        if teacher_id: qs = qs.filter(docente_id=teacher_id)
        if course_id: qs = qs.filter(curso_id=course_id)
        if level: qs = qs.filter(curso__nivel__iexact=level)
        rows = []
        for a in qs:
            relation = CursoCursaMaterias.objects.filter(id_curso=a.curso, id_materia=a.materia).first()
            rows.append(_row(headers, _text(a.docente), a.curso.nivel, f"{a.curso.anio}° {a.curso.comision} - {a.materia.nombre}", relation.horarios if relation else "Sin horario cargado"))
        return headers, rows, "Se muestran las asignaciones docente-curso-materia explícitamente registradas."

    if code == "R-03":
        headers = ["Nivel", "Curso", "Legajo", "Apellido", "Nombre"]
        rows = [_row(headers, a.id_curso.nivel if a.id_curso else "Sin nivel", f"{a.id_curso.anio}° {a.id_curso.comision}" if a.id_curso else "Sin curso", a.legajo, a.id_persona.apellido, a.id_persona.nombre) for a in alumnos.order_by("id_curso__nivel", "id_curso__anio", "id_curso__comision", "id_persona__apellido", "id_persona__nombre")]
        return headers, rows, "Listado de alumnos agrupado por el curso actual de la ficha."

    if code == "R-04":
        headers = ["Nivel", "Curso", "Materia", "Docente", "Alumno", "Legajo"]
        relations = CursoCursaMaterias.objects.select_related("id_curso", "id_materia").filter(id_curso__in=Curso.objects.all())
        if course_id: relations = relations.filter(id_curso_id=course_id)
        if subject_id: relations = relations.filter(id_materia_id=subject_id)
        if level: relations = relations.filter(id_curso__nivel__iexact=level)
        rows = []
        for rel in relations:
            teachers = list(assignments.filter(curso=rel.id_curso, materia=rel.id_materia))
            if teacher_id: teachers = [t for t in teachers if t.docente_id == teacher_id]
            students = alumnos.filter(id_curso=rel.id_curso)
            for student in students:
                teacher_names = ", ".join(_text(t.docente) for t in teachers) or "Asignación docente por curso pendiente"
                rows.append(_row(headers, rel.id_curso.nivel, f"{rel.id_curso.anio}° {rel.id_curso.comision}", rel.id_materia.nombre, teacher_names, _text(student), student.legajo))
        return headers, rows, "La materia se vincula al curso; el docente solo se atribuye cuando existe asignación explícita."

    if code == "R-05":
        headers = ["Nivel", "Docente", "Materias a cargo", "Cursos"]
        qs = assignments
        if teacher_id: qs = qs.filter(docente_id=teacher_id)
        if course_id: qs = qs.filter(curso_id=course_id)
        if subject_id: qs = qs.filter(materia_id=subject_id)
        if level: qs = qs.filter(curso__nivel__iexact=level)
        grouped = defaultdict(lambda: {"subjects": set(), "courses": set()})
        for a in qs:
            key = (a.curso.nivel, a.docente_id, _text(a.docente))
            grouped[key]["subjects"].add(a.materia.nombre)
            grouped[key]["courses"].add(f"{a.curso.anio}° {a.curso.comision}")
        rows = [_row(headers, nivel_name, teacher_name, ", ".join(sorted(v["subjects"])), ", ".join(sorted(v["courses"]))) for (nivel_name, _, teacher_name), v in sorted(grouped.items())]
        return headers, rows, "Los docentes se agrupan por sus asignaciones académicas registradas para cada curso."

    if code == "R-06":
        headers = ["Deporte", "Alumno", "Curso", "Nivel"]
        rows = []
        seen = set()
        enrollments = active_sports
        if sport_id: enrollments = enrollments.filter(grupo__disciplina_id=sport_id)
        if course_id: enrollments = enrollments.filter(alumno__id_curso_id=course_id)
        if level: enrollments = enrollments.filter(alumno__id_curso__nivel__iexact=level)
        if student_id: enrollments = enrollments.filter(alumno_id=student_id)
        for e in enrollments:
            key=(e.alumno_id,e.grupo.disciplina_id)
            seen.add(key)
            rows.append(_row(headers,e.grupo.disciplina.nombre,_text(e.alumno),f"{e.alumno.id_curso.anio}° {e.alumno.id_curso.comision}" if e.alumno.id_curso else "Sin curso",e.alumno.id_curso.nivel if e.alumno.id_curso else "Sin nivel"))
        legacy = alumnos.exclude(id_disciplina__isnull=True)
        if sport_id: legacy=legacy.filter(id_disciplina_id=sport_id)
        for student in legacy.select_related("id_disciplina"):
            key=(student.pk,student.id_disciplina_id)
            if key not in seen:
                rows.append(_row(headers,student.id_disciplina.nombre,_text(student),f"{student.id_curso.anio}° {student.id_curso.comision}" if student.id_curso else "Sin curso",student.id_curso.nivel if student.id_curso else "Sin nivel"))
        return headers, rows, "Se incluyen las inscripciones estructuradas y las relaciones deportivas heredadas."

    if code == "R-07":
        headers = ["Deporte", "Nivel", "Día", "Horario", "Profesor responsable", "Alumnos"]
        groups = InscripcionDeportiva.objects.none()
        group_qs = GrupoDeportivo.objects.select_related("disciplina", "profesor_responsable__id_persona").all()
        if sport_id: group_qs=group_qs.filter(disciplina_id=sport_id)
        if level: group_qs=group_qs.filter(nivel__iexact=level)
        if teacher_id: group_qs=group_qs.filter(profesor_responsable_id=teacher_id)
        rows=[]
        for group in group_qs:
            enrolls=InscripcionDeportiva.objects.filter(grupo=group,estado="Activa").select_related("alumno__id_persona")
            if student_id: enrolls=enrolls.filter(alumno_id=student_id)
            if course_id: enrolls=enrolls.filter(alumno__id_curso_id=course_id)
            students=[_text(e.alumno) for e in enrolls]
            rows.append(_row(headers,group.disciplina.nombre,group.nivel,group.dia_semana,f"{group.hora_inicio:%H:%M}-{group.hora_fin:%H:%M}",_text(group.profesor_responsable),", ".join(students)))
        return headers, rows, "Los grupos con nivel, horario y profesor explícitos aparecen aquí; la relación heredada no se transforma automáticamente."

    if code == "R-08":
        headers = ["Recorrido", "Alumno", "Curso", "Nivel"]
        qs = active_transport
        if route_id: qs=qs.filter(recorrido_id=route_id)
        if course_id: qs=qs.filter(alumno__id_curso_id=course_id)
        if student_id: qs=qs.filter(alumno_id=student_id)
        if level: qs=qs.filter(alumno__id_curso__nivel__iexact=level)
        rows=[_row(headers,e.recorrido.nombre,_text(e.alumno),f"{e.alumno.id_curso.anio}° {e.alumno.id_curso.comision}" if e.alumno.id_curso else "Sin curso",e.alumno.id_curso.nivel if e.alumno.id_curso else "Sin nivel") for e in qs]
        return headers, rows, "Se listan las asignaciones de recorrido activas; no se exponen domicilios ni teléfonos."
    return [], [], "Seleccione un reporte válido."


@require_GET
def reportes(request):
    persona, role = obtener_datos_sesion(request)
    if not persona:
        return redirect("login")
    admin = role in {"dashboard-administrativo", "dashboard-directivo"}
    ConfiguracionTecnicaSingleton()
    code = request.GET.get("reporte", "R-01")
    if code not in REPORTS: code = "R-01"
    filters = _filters(request)
    if role == "dashboard-padres" and code == "R-01":
        tutor = Tutor.objects.filter(id_persona=persona).first()
        linked = Alumno.objects.filter(tutortutoraalumno__id_tutor=tutor).distinct() if tutor else Alumno.objects.none()
        filters["alumno"] = request.GET.get("alumno", "") if linked.filter(pk=request.GET.get("alumno")).exists() else ""
        allowed_students = linked.select_related("id_persona")
        force_empty = not filters["alumno"]
    elif role == "dashboard-alumno" and code == "R-01":
        own = Alumno.objects.filter(id_persona=persona).first()
        filters["alumno"] = str(own.pk) if own else ""
        allowed_students = Alumno.objects.filter(pk=own.pk) if own else Alumno.objects.none()
        force_empty = own is None
    elif role == "dashboard-docente" and code == "R-02":
        own = Docente.objects.filter(id_persona=persona).first()
        filters["docente"] = str(own.pk) if own else ""
        allowed_students = Alumno.objects.none()
        force_empty = own is None
    elif admin:
        allowed_students = Alumno.objects.select_related("id_persona")
        force_empty = False
    else:
        return HttpResponseForbidden("El reporte solicitado no está habilitado para su rol.")
    headers, rows, note = build_report(code, filters)
    if force_empty:
        rows = []
    return render(request, "core/reportes.html", {
        "reportes": REPORTS, "codigo": code, "titulo": REPORTS[code],
        "filtros": filters, "headers": headers, "rows": rows,
        "nota": note, "alumnos": allowed_students.order_by("id_persona__apellido", "id_persona__nombre"),
        "docentes": Docente.objects.select_related("id_persona").order_by("id_persona__apellido", "id_persona__nombre"),
        "cursos": Curso.objects.all().order_by("nivel", "anio", "comision"),
        "materias": Materia.objects.all().order_by("nombre"),
        "deportes": DisciplinaDeportiva.objects.all().order_by("nombre"),
        "recorridos": RecorridoTransporte.objects.filter(activo=True),
        "niveles": Curso.objects.order_by("nivel").values_list("nivel", flat=True).distinct(),
        "admin": admin,
        "selector_alumno": role == "dashboard-padres",
        "selector_docente": role == "dashboard-docente",
    })


@require_GET
def auditoria(request):
    _, denied = _authorized(request)
    if denied:
        return denied
    return render(request, "core/auditoria.html", {
        "cambios": AuditoriaCambio.objects.select_related("usuario").all()[:250],
    })
