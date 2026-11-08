"""El flujo de demostración completo: datos demo -> facturas -> tutor ve su deuda."""
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient


class SeedDemoTests(TestCase):
    def test_seed_demo_permite_entrar_facturar_y_ver_la_deuda(self):
        call_command('seed_demo', stdout=StringIO())

        salida = StringIO()
        call_command('generar_facturas', '--periodo', '2026-11', stdout=salida)
        self.assertNotIn('No facturado', salida.getvalue())

        api = APIClient()
        login = api.post('/api/login/', {'usuario': 'tutor_demo', 'password': 'tutor123'}, format='json')
        self.assertEqual(login.status_code, 200)
        api.credentials(HTTP_AUTHORIZATION='Bearer ' + login.json()['access'])

        hijos = api.get('/api/alumnos/').json()
        self.assertEqual(len(hijos), 2)
        for hijo in hijos:
            deuda = api.get(f"/api/deuda/?alumno={hijo['legajo']}").json()
            self.assertGreater(Decimal(deuda['total_deuda']), 0)
