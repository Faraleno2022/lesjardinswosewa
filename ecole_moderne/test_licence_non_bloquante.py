from io import StringIO
from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from ecole_moderne.licence_middleware import LicenceMiddleware
from run_server import check_license, show_banner


class LicenceNonBloquanteTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get('/eleves/liste/')

    @patch(
        'ecole_moderne.licence_middleware._check_integrity_cached',
        return_value={'valid': True, 'reason': ''},
    )
    def test_application_intacte_reste_accessible_sans_controle_licence(
        self, _integrity
    ):
        middleware = LicenceMiddleware(lambda request: HttpResponse('Application'))

        response = middleware(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'Application')
        self.assertNotContains(response, "Votre essai expire")
        self.assertNotContains(response, "Votre licence a expiré")

    @patch(
        'ecole_moderne.licence_middleware._check_integrity_cached',
        return_value={'valid': False, 'reason': 'tampered'},
    )
    def test_integrite_invalide_reste_bloquante(self, _integrity):
        middleware = LicenceMiddleware(lambda request: HttpResponse('Application'))

        response = middleware(self.request)

        self.assertEqual(response.status_code, 403)
        self.assertContains(
            response, 'Application corrompue', status_code=403
        )

    @patch('run_server.os._exit')
    @patch('run_server.show_activation_window')
    def test_demarrage_ne_demande_plus_activation(
        self, activation_window, process_exit
    ):
        self.assertTrue(check_license())
        activation_window.assert_not_called()
        process_exit.assert_not_called()

    def test_banniere_ne_montre_plus_compte_a_rebours_essai(self):
        sortie = StringIO()
        with patch('sys.stdout', sortie):
            show_banner(8000, {'trial': True, 'days_left': 5})

        texte = sortie.getvalue()
        self.assertIn('Accès actif', texte)
        self.assertNotIn('Essai', texte)
        self.assertNotIn('5j restant', texte)
