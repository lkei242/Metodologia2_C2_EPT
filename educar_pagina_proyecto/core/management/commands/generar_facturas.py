"""Genera las facturas de un período para todos los alumnos activos.

Uso:
    python manage.py generar_facturas --periodo 2026-11

Es idempotente: si la factura del alumno ya existe, no la duplica.
Los alumnos que no se pueden facturar (falta curso, tutor o valor) se informan al final.
"""
from django.core.management.base import BaseCommand, CommandError

from core.facturacion import FacturacionError, generar_factura, validar_periodo
from core.models import Alumno


class Command(BaseCommand):
    help = 'Genera las facturas del período indicado para los alumnos activos.'

    def add_arguments(self, parser):
        parser.add_argument('--periodo', required=True, help='Período en formato AAAA-MM')

    def handle(self, *args, **options):
        try:
            periodo = validar_periodo(options['periodo'])
        except FacturacionError as exc:
            raise CommandError(str(exc))

        creadas = 0
        existentes = 0
        errores = []
        for alumno in Alumno.objects.filter(estado='Activo').select_related('id_curso', 'id_persona'):
            try:
                _, creada = generar_factura(alumno, periodo)
            except FacturacionError as exc:
                errores.append(str(exc))
                continue
            if creada:
                creadas += 1
            else:
                existentes += 1

        self.stdout.write(f'Período {periodo}: {creadas} facturas creadas, {existentes} ya existían.')
        for error in errores:
            self.stdout.write(self.style.WARNING(f'No facturado: {error}'))
