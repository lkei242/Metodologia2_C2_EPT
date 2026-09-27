# Generated and made tolerant of the legacy SQLite column already present in some project databases.
import django.db.models.deletion
from django.db import migrations, models


def ensure_alumno_estado(apps, schema_editor):
    connection = schema_editor.connection
    table = "alumno"
    if table not in connection.introspection.table_names():
        return
    columns = {column.name for column in connection.introspection.get_table_description(schema_editor.connection.cursor(), table)}
    if "estado" not in columns:
        qn = schema_editor.quote_name
        schema_editor.execute(
            f"ALTER TABLE {qn(table)} ADD COLUMN {qn('estado')} varchar(20) NOT NULL DEFAULT 'Activo'"
        )


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="DocenteCursoMateria",
            fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"))],
            options={"db_table": "docente_curso_materia"},
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(ensure_alumno_estado, migrations.RunPython.noop)],
            state_operations=[migrations.AddField(
                model_name="alumno", name="estado",
                field=models.CharField(choices=[("Activo", "Activo"), ("Inactivo", "Inactivo")], default="Activo", max_length=20),
            )],
        ),
        migrations.AddField(
            model_name="docente", name="estado",
            field=models.CharField(choices=[("Activo", "Activo"), ("Inactivo", "Inactivo")], default="Activo", max_length=20),
        ),
        migrations.AddField(
            model_name="docentecursomateria", name="curso",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_docentes", to="core.curso"),
        ),
        migrations.AddField(
            model_name="docentecursomateria", name="docente",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_academicas", to="core.docente"),
        ),
        migrations.AddField(
            model_name="docentecursomateria", name="materia",
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="asignaciones_docentes", to="core.materia"),
        ),
        migrations.AddConstraint(
            model_name="inscripcion",
            constraint=models.UniqueConstraint(condition=models.Q(("estado", "Activa")), fields=("legajo_alumno",), name="uniq_inscripcion_activa_por_alumno"),
        ),
        migrations.AddConstraint(
            model_name="docentecursomateria",
            constraint=models.UniqueConstraint(fields=("docente", "curso", "materia"), name="uniq_docente_curso_materia"),
        ),
    ]
