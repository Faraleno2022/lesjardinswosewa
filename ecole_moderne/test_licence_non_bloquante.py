import json
import os
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from ecole_moderne.integrity_middleware import IntegrityMiddleware
import run_server
from run_server import show_banner


class LicenceNonBloquanteTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/eleves/liste/')

    @patch(
        'ecole_moderne.integrity_middleware._check_integrity_cached',
        return_value={'valid': True, 'reason': ''},
    )
    def test_application_intacte_reste_accessible_sans_controle_licence(
        self, _integrity
    ):
        middleware = IntegrityMiddleware(lambda request: HttpResponse('Application'))

        response = middleware(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'Application')
        self.assertNotContains(response, "Votre essai expire")
        self.assertNotContains(response, "Votre licence a expiré")

    @patch(
        'ecole_moderne.integrity_middleware._check_integrity_cached',
        return_value={'valid': False, 'reason': 'tampered'},
    )
    def test_integrite_invalide_reste_bloquante(self, _integrity):
        middleware = IntegrityMiddleware(lambda request: HttpResponse('Application'))

        response = middleware(self.request)

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response, 'Application corrompue', status_code=403
        )

    def test_banniere_ne_montre_plus_compte_a_rebours_essai(self):
        sortie = StringIO()
        with patch('sys.stdout', sortie):
            show_banner(8000)

        texte = sortie.getvalue()
        self.assertIn('aucune licence requise', texte)
        self.assertNotIn('Essai', texte)

    def test_ancienne_configuration_sync_dans_sous_dossier_est_chargee(self):
        with TemporaryDirectory() as dossier:
            chemin = Path(dossier) / 'sync' / '_config.json'
            chemin.parent.mkdir()
            chemin.write_text(
                json.dumps({
                    'MYSCHOOL_SYNC_SERVER_URL': 'https://ecole.example',
                    'MYSCHOOL_SYNC_ECOLE_ID': 1,
                    'MYSCHOOL_SYNC_DEVICE_ID': 'poste-test',
                    'MYSCHOOL_SYNC_TOKEN': 'jeton-test',
                }),
                encoding='utf-8',
            )

            with patch.object(run_server, 'BASE_DIR', dossier), patch.dict(
                os.environ, {'APPDATA': dossier}, clear=True
            ):
                run_server._load_sync_config()

                self.assertEqual(
                    os.environ['MYSCHOOL_SYNC_SERVER_URL'],
                    'https://ecole.example',
                )
                self.assertEqual(os.environ['MYSCHOOL_SYNC_ECOLE_ID'], '1')
                self.assertEqual(
                    os.environ['MYSCHOOL_SYNC_DEVICE_ID'], 'poste-test'
                )
                self.assertEqual(os.environ['MYSCHOOL_SYNC_TOKEN'], 'jeton-test')
