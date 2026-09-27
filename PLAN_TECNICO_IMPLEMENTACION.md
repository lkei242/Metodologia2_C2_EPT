# Análisis y plan técnico de implementación

## Especificación revisada

Se tomaron como referencia el PDF de Parte 2, el texto complementario y la captura de reportes/reglas adjuntos a la conversación. Para este trabajo, las historias priorizadas por Sprint 1 son HU-01, HU-02, HU-03, HU-05 y HU-08. La captura complementa el alcance con R-01 a R-08 y RN-01 a RN-12.

El sistema existente es un proyecto Django con SQLite, sesiones propias y roles inferidos desde las relaciones de `Persona` con `PersonalAdministrativo`, `Directivo`, `Docente`, `Tutor`, `Preceptor` o `Alumno`. Se conservó esa arquitectura y se añadieron módulos Django compatibles.

## Comparación entre documentación y código

| Área | Estado después de los cambios | Observación |
|---|---|---|
| HU-01 alumnos | Implementada | Alta/edición, DNI único, legajo autogenerado, curso, estado, comedor y transporte. Validación en servidor. |
| HU-02 docentes | Implementada | Alta/edición y asignación explícita docente-curso-materia. |
| HU-03 cursos y materias | Implementada | Alta de curso/materia, asociación y horario; curso exige nivel. El nivel sigue siendo el texto existente del modelo `Curso`. |
| HU-05 inscripción a cursado | Implementada | Una inscripción activa por alumno; cambio de curso conserva la inscripción anterior finalizada. |
| HU-08 usuarios y permisos | Implementada para rutas tocadas | Las pantallas y acciones nuevas se restringen por rol en servidor. También se protegieron las acciones administrativas sensibles y el alta de usuario. |
| HU-04 / HU-06 deportes | Implementada con conciliación de datos heredados | Grupos estructurados con profesor, nivel, día y horario; máximo dos deportes activos y detección de solapamientos. Tutor gestiona únicamente hijos vinculados. |
| HU-07 transporte y comedor | Implementada | Se permiten hasta cuatro recorridos configurables; la asignación es opcional y modificable. Comedor solo lo administra personal autorizado. |
| HU-09 a HU-16 / R-01 a R-08 | Implementados | Consultas sobre los modelos existentes y los vínculos explícitos nuevos; filtros, encabezados, permisos y estados vacíos. |
| HU-17 auditoría | Implementada en flujos modificados | El Observer registra actor, acción, entidad y campos después del commit. Auditoría visible solo para Administración/Dirección. |

## Tareas y dependencias

| Orden | Tarea | Módulos | Dependencia | Comprobación |
|---|---|---|---|---|
| 1 | Mantener inventario y respaldo de la base SQLite antes de migrar. | `db.sqlite3`, migraciones | Ninguna | Comparar conteos y verificar que el respaldo abre. |
| 2 | Completar entidades/relaciones para estados, asignación docente-curso-materia, grupos deportivos, inscripciones deportivas, recorridos y auditoría. | `core/models.py`, `core/migrations/0002*`, `0003*` | 1 | `migrate`, restricciones únicas y consultas a filas existentes. |
| 3 | Implementar fichas administrativas de alumnos/docentes y configuración académica. | `management_forms.py`, `management_views.py`, templates `gestion_*` | 2 | Alta, edición, DNI duplicado, materia no asignada y permisos por rol. |
| 4 | Preservar historial al cambiar curso y restringir duplicados activos. | `management_views.py`, modelo `Inscripcion` | 2 | Pruebas de cambio, duplicado y unicidad en base. |
| 5 | Configurar reglas de deporte y transporte en servicios de dominio. | `business_forms.py`, `domain_services.py`, `service_views.py` | 2 | Máximo de dos, solapamiento, fin anterior al inicio, cuatro recorridos y cambios de recorrido. |
| 6 | Añadir gestión familiar limitada a las relaciones tutor-hijo existentes. | `service_views.py`, `familia_servicios.html`, portal del tutor | 3 y 5 | Tutor vinculado puede operar; otro tutor o alumno no vinculado recibe 403. |
| 7 | Implementar adaptador de consultas y reportes R-01 a R-08. | `patterns.py`, `reporting_views.py`, `reportes.html` | 2 y asignaciones disponibles | Comparar columnas y filtros con la especificación usando fixtures conocidos y revisar permisos. |
| 8 | Registrar cambios confirmados y restringir consulta de auditoría. | `domain_services.py`, llamadas desde vistas y `auditoria.html` | Flujos 3–7 | Confirmar registro tras commit y ausencia de registro si la transacción revierte. |
| 9 | Integrar navegación y estilos adaptables. | paneles, templates `gestion_*`, `familia_servicios.html`, `gestion.css` | 3–8 | Renderizar paneles, probar ancho móvil/escritorio y estados vacíos. |
| 10 | Ejecutar pruebas funcionales, de permisos y migración; registrar brechas de datos heredados. | `core/tests.py`, `manage.py` | 1–9 | Suite de pruebas, `check`, `makemigrations --check` y verificación de SQLite real. |

## Patrones de diseño

- **Singleton:** `ConfiguracionTecnicaSingleton` mantiene límites técnicos inmutables por proceso (dos deportes, cuatro recorridos).
- **Adapter:** `DjangoReportesAdapter` concentra el acceso de reportes a modelos y relaciones existentes.
- **Observer:** `AuditoriaObserver` recibe cambios confirmados con `transaction.on_commit`, evitando auditar operaciones revertidas.

## Diferencias y datos que requieren definición/carga

1. La SQLite tenía 99 alumnos, 28 docentes y 96 inscripciones; no tenía la relación explícita docente-curso-materia. No se infirió qué docente corresponde a qué curso a partir de las dos asociaciones heredadas. Administración debe cargar esas asignaciones para completar R-02/R-05 y el dato docente de R-04.
2. Ocho alumnos conservaban deporte en el campo legado `Alumno.id_disciplina`, sin día/horario por grupo. El reporte los muestra como heredados. Para validar conflictos, Administración debe elegir explícitamente el grupo y confirmar su horario al conciliarlo; el sistema no inventa el horario.
3. No había recorridos ni nombres definidos en la base o en los documentos adjuntos. El sistema permite configurar hasta cuatro y cambiar la asignación, pero Administración debe dar de alta sus nombres.
4. La auditoría empieza a registrar las operaciones instrumentadas desde esta versión; no reconstruye cambios históricos anteriores.

## Verificación ejecutada

- `python manage.py test core --verbosity 1`: 27 pruebas aprobadas, incluidos accesos a los seis paneles por rol.
- `python manage.py check`: sin errores.
- `python manage.py makemigrations --check --dry-run`: sin cambios pendientes.
- `git diff --check`: sin errores de formato.
- Migraciones 0002 y 0003 aplicadas a SQLite después de guardar una copia previa; conteos existentes sin cambios y sin duplicados en inscripciones activas.

La prueba automatizada informa una advertencia inocua: no existe el directorio opcional `staticfiles/` durante las pruebas. La aplicación usa archivos estáticos fuente bajo `core/static/`.
