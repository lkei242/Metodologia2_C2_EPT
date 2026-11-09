"""El flujo de demostración completo: datos demo -> facturas -> tutor ve su deuda."""
import os
import secrets
import tempfile
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from core.models import Usuario
from core.seguridad import guardar_contrasenia


class SeedDemoTests(TestCase):
    def test_seed_demo_permite_entrar_facturar_y_ver_la_deuda(self):
        # El seed escribe sus contrasenias en un archivo temporal, no en el del proyecto.
        with tempfile.TemporaryDirectory() as carpeta:
            with override_settings(SEED_CREDENCIALES_PATH=os.path.join(carpeta, 'credenciales.txt')):
                call_command('seed_demo', stdout=StringIO())

        # La contrasenia de la demo es aleatoria: la fijamos solo dentro de esta base de prueba.
        clave = secrets.token_urlsafe(9)
        Usuario.objects.filter(nombre_usuario='tutor_demo').update(contrasenia=guardar_contrasenia(clave))

        salida = StringIO()
        call_command('generar_facturas', '--periodo', '2026-11', stdout=salida)
        self.assertNotIn('No facturado', salida.getvalue())

        api = APIClient()
        login = api.post('/api/login/', {'usuario': 'tutor_demo', 'password': clave}, format='json')
        self.assertEqual(login.status_code, 200)
        api.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])

        hijos = api.get('/api/alumnos/').json()
        self.assertEqual(len(hijos), 2)
        for hijo in hijos:
            deuda = api.get(f"/api/deuda/?alumno={hijo['legajo']}").json()
            self.assertGreater(Decimal(deuda['total_deuda']), 0)
