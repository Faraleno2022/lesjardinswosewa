from django.core.cache import cache
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from ecole_moderne.security_middleware import SecurityMiddleware


class SecurityMiddlewarePathTraversalTests(SimpleTestCase):
    client_ip = '198.51.100.42'

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityMiddleware(lambda request: HttpResponse())
        cache.delete(f'blocked_ip_{self.client_ip}')
        cache.delete(self.middleware._rate_limit_cache_key(self.client_ip))

    def tearDown(self):
        cache.delete(f'blocked_ip_{self.client_ip}')
        cache.delete(self.middleware._rate_limit_cache_key(self.client_ip))

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


class SecurityMiddlewareRateLimitTests(SimpleTestCase):
    client_ip = '198.51.100.77'

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = SecurityMiddleware(lambda request: HttpResponse())
        cache.delete(self.middleware._rate_limit_cache_key(self.client_ip))

    def tearDown(self):
        cache.delete(self.middleware._rate_limit_cache_key(self.client_ip))

    @override_settings(
        SECURITY_RATE_LIMIT_REQUESTS=2,
        SECURITY_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    def test_limite_retourne_429_sans_prolonger_la_fenetre(self):
        for _ in range(2):
            request = self.factory.get('/', REMOTE_ADDR=self.client_ip)
            self.assertIsNone(self.middleware.process_request(request))

        response = self.middleware.process_request(
            self.factory.get('/', REMOTE_ADDR=self.client_ip)
        )

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response['Retry-After'], '60')
        self.assertContains(
            response, 'Trop de requêtes', status_code=429
        )

    def test_ressources_et_api_techniques_ne_sont_pas_comptees(self):
        chemins = (
            '/static/css/app.css',
            '/media/images/photo.jpg',
            '/favicon.ico',
            '/robots.txt',
            '/sitemap.xml',
            '/api/v1/sync/state/',
            '/api/v1/updates/latest/',
        )

        for chemin in chemins:
            with self.subTest(chemin=chemin):
                request = self.factory.get(chemin, REMOTE_ADDR=self.client_ip)
                self.assertIsNone(self.middleware.process_request(request))

        self.assertEqual(
            cache.get(self.middleware._rate_limit_cache_key(self.client_ip), 0),
            0,
        )

    def test_x_real_ip_pythonanywhere_est_prioritaire(self):
        request = self.factory.get(
            '/',
            REMOTE_ADDR='10.0.0.5',
            HTTP_X_REAL_IP=self.client_ip,
            HTTP_X_FORWARDED_FOR='203.0.113.99, 10.0.0.5',
        )

        self.assertEqual(self.middleware.get_client_ip(request), self.client_ip)
