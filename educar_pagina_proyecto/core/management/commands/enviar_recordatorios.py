import datetime
from django.core.management.base import BaseCommand
from core.correos import enviar_recordatorio_ultimo_dia_habil


class Command(BaseCommand):
    help = "Envía por correo el recordatorio de pago del último día hábil a los tutores (G6 / RF-M08)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fecha",
            type=str,
            help="Fecha de referencia en formato YYYY-MM-DD para pruebas o demostración.",
        )

    def handle(self, *args, **options):
        fecha_str = options.get("fecha")
        fecha = None
        if fecha_str:
            try:
                fecha = datetime.datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except ValueError:
                self.stderr.write(self.style.ERROR("Formato de fecha inválido. Utilice YYYY-MM-DD."))
                return

        self.stdout.write(self.style.NOTICE("Iniciando envío de recordatorios de pago..."))
        resultado = enviar_recordatorio_ultimo_dia_habil(fecha)
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Recordatorios procesados para fecha {resultado['fecha']}: "
                f"{resultado['enviados']} enviados, {resultado['fallidos']} fallidos."
            )
        )
