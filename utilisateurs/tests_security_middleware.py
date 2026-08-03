from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from ecole_moderne.security_middleware import SecurityMiddleware


class SecurityMiddlewarePathTraversalTests(SimpleTestCase):
    client_ip = '198.51.100.42'

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityMiddleware(lambda request: HttpResponse())
        cache.delete(f'blocked_ip_{self.client_ip}')
        cache.delete(f'rate_limit_{self.client_ip}')

    def tearDown(self):
        cache.delete(f'blocked_ip_{self.client_ip}')
        cache.delete(f'rate_limit_{self.client_ip}')

    def test_url_de_redirection_encodee_n_est_pas_un_path_traversal(self):
        request = self.factory.get(
            '/paiements/ajouter/7/',
            {'next': '/eleves/ajouter/?classe_id=8'},
            HTTP_X_FORWARDED_FOR=self.client_ip,
        )

        self.assertIn('%2Feleves%2Fajouter%2F', request.get_full_path())
        self.assertFalse(self.middleware.detect_path_traversal(request))
        self.assertIsNone(self.middleware.process_request(request))
        self.assertFalse(cache.get(f'blocked_ip_{self.client_ip}', False))

    def test_les_vrais_path_traversal_restent_detectes(self):
        chemins_malveillants = (
            '/media/../settings.py',
            '/media/%2e%2e%2fsettings.py',
            '/telecharger/?fichier=..%2Fsettings.py',
            '/telecharger/?fichier=%2e%2e%5csettings.py',
        )

        for chemin in chemins_malveillants:
            with self.subTest(chemin=chemin):
                request = self.factory.get(chemin)
                self.assertTrue(
                    self.middleware.detect_path_traversal(request),
                    msg=f'Le chemin malveillant doit être détecté : {chemin}',
                )
