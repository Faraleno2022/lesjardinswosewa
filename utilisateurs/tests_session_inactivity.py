import time

from django.conf import settings
from django.contrib.auth import SESSION_KEY, get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(SESSION_IDLE_TIMEOUT_SECONDS=60)
class SessionInactivityTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='session-admin',
            email='session@test.local',
            password='secret-session',
        )
        self.client.force_login(self.user)

    def _set_last_activity(self, value):
        session = self.client.session
        session['last_activity'] = value
        session['phone_verified'] = True
        session['phone_verified_at'] = time.time()
        session.save()

    def test_session_expiree_deconnecte_et_redirige(self):
        self._set_last_activity(time.time() - 61)

        response = self.client.get(reverse('admin:index'))

        self.assertRedirects(
            response,
            reverse('utilisateurs:login'),
            fetch_redirect_response=False,
        )
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_session_expiree_sur_api_retourne_401_json(self):
        self._set_last_activity(time.time() - 61)

        response = self.client.get(
            reverse('synchronisation:state'),
            HTTP_X_SESSION_BACKGROUND='1',
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['error'], 'Session expirée pour inactivité.')
        self.assertNotIn(SESSION_KEY, self.client.session)

    def test_activite_humaine_renouvelle_le_delai(self):
        ancienne_activite = time.time() - 30
        self._set_last_activity(ancienne_activite)

        response = self.client.get(reverse('admin:index'))

        self.assertEqual(response.status_code, 200)
        session = self.client.session
        self.assertGreater(session['last_activity'], ancienne_activite)
        self.assertLessEqual(session.get_expiry_age(), 60)

    def test_polling_de_synchronisation_ne_renouvelle_pas_activite(self):
        ancienne_activite = time.time() - 30
        self._set_last_activity(ancienne_activite)

        response = self.client.get(
            reverse('synchronisation:state'),
            HTTP_X_SESSION_BACKGROUND='1',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session['last_activity'], ancienne_activite)

    def test_page_authentifiee_contient_le_minuteur_navigateur(self):
        self._set_last_activity(time.time())

        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="session-logout-form"')
        self.assertContains(response, 'var DELAI_MS = Number("60") * 1000;')
        self.assertContains(response, "'X-Session-Background': '1'", count=2)

    def test_middleware_est_place_apres_session_auth_et_messages(self):
        middlewares = list(settings.MIDDLEWARE)
        securite = middlewares.index(
            'ecole_moderne.security_middleware.SessionSecurityMiddleware'
        )

        self.assertLess(
            middlewares.index('django.contrib.sessions.middleware.SessionMiddleware'),
            securite,
        )
        self.assertLess(
            middlewares.index('django.contrib.auth.middleware.AuthenticationMiddleware'),
            securite,
        )
        self.assertLess(
            middlewares.index('django.contrib.messages.middleware.MessageMiddleware'),
            securite,
        )
