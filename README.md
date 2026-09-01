# Educar para Transformar - MATECH

## Descripción Breve
**Educar para Transformar** es un sistema web de gestión escolar e institucional desarrollado con el framework **Django**. Está diseñado para el centro educativo "Educar para Transformar", permitiendo la centralización de procesos académicos, administrativos, financieros y de servicios institucionales en una arquitectura por capas eficiente y segura.

---

## Funcionalidades Principales

### 1. Gestión Académica (Vista de Profesores, Alumnos y Preceptores)
- **Inscripción de alumnos postulantes**: Registro de solicitudes de inscripción con validación de edad y datos personales por nivel educativo.
- **Consulta de materias y horarios**: Visualización organizada por días de la semana de asignaturas y disciplinas.
- **Calificaciones y seguimiento**: Carga de notas por bimensualidades y cálculo automático de promedios académicos.
- **Control y justificación de asistencia**: Registro de presentismo, ausencias y tardanzas, con opción de adjuntar certificados de justificación (PDF, PNG, JPG).

### 2. Gestión Administrativa y Directiva
- **Dashboard administrativo y directivo**: Control centralizado de usuarios, roles y autorizaciones.
- **Gestión de comunicados y noticias**: Publicación de noticias institucionales y avisos dirigidos a cursos específicos.
- **Organización de cursos y comisiones**: Asignación de docentes y preceptores a cursos.

### 3. Gestión Financiera
- **Gestión de cuotas y pagos**: Consulta de estado de cuotas pagadas o pendientes por tutor/alumno.
- **Aranceles por nivel**: Definición y actualización de valores de matriculación y mensualidades por nivel educativo.

### 4. Gestión de Servicios e Instalaciones
- **Disciplinas deportivas**: Inscripción de alumnos a deportes y consulta de horarios de instalaciones.
- **Reservas y turnos**: Administración y pedido de turnos para espacios escolares (aulas, biblioteca, gimnasio, laboratorios).

---

## Cómo Ejecutar el Programa

### Requisitos Previos
- Python 3.10 o superior instalado.
- Gestor de paquetes `pip`.

### Pasos de Instalación y Ejecución

1. **Clonar o descargar el repositorio**:
   ```bash
   git clone <URL_DEL_REPOSITORIO>
   cd MATECH/educar_pagina/educar_pagina_proyecto
   ```

2. **Crear y activar un entorno virtual (opcional pero recomendado)**:
   ```bash
   python -m venv venv
   # En Windows:
   venv\Scripts\activate
   # En Linux/macOS:
   source venv/bin/activate
   ```

3. **Instalar dependencias necesarias**:
   ```bash
   pip install django requests resend whitenoise
   ```

4. **Aplicar las migraciones de la base de datos**:
   ```bash
   python manage.py migrate
   ```

5. **Iniciar el servidor de desarrollo de Django**:
   ```bash
   python manage.py runserver
   ```

6. **Acceder a la aplicación**:
   Abre tu navegador web e ingresa a: `http://127.0.0.1:8000/`

---

## Arquitectura del Sistema

El sistema implementa una **arquitectura en 3 capas**:
1. **Capa de Presentación**: Interfaces HTML5/CSS3 dinámicas renderizadas mediante plantillas Django.
2. **Capa de Lógica de Negocio**: Controladores (`views.py`), validaciones (`forms.py`) y procesadores de contexto (`context_processors.py`).
3. **Capa de Datos**: Modelos relacionales ORM de Django (`models.py`) sobre SQLite / PostgreSQL / MySQL.

---

## Refactorizaciones Aplicadas (Actividad 3)

1. **División de funciones extensas (SRP)**:
   - Abstracción de validaciones en `InscripcionForm` ([core/forms.py](file:///D:/Bibliotecas/Escritorio/MATECH/educar_pagina/educar_pagina_proyecto/core/forms.py)).
   - Descomposición de la vista monolítica `dashboard_alumno` en funciones auxiliares (`_obtener_resumen_horarios`, `_calcular_resumen_notas`, `_procesar_justificacion_asistencia`).
2. **Eliminación de código duplicado**:
   - Creación del context processor `datos_sesion_context` ([core/context_processors.py](file:///D:/Bibliotecas/Escritorio/MATECH/educar_pagina/educar_pagina_proyecto/core/context_processors.py)) para inyectar automáticamente información de sesión (`persona`, `dashboard_url`) en todas las vistas.

---

## Integrantes
- **Luka Burgos** (Burgos Salvaedo Luka Edgardo)
- **Romero Germán**
