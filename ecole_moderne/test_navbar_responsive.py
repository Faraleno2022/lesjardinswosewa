from django.test import SimpleTestCase, override_settings


@override_settings(ALLOWED_HOSTS=['testserver'])
class NavbarResponsiveTests(SimpleTestCase):
    def setUp(self):
        self.response = self.client.get('/rapport-scolaire/')

    def test_navigation_conserve_la_disposition_initiale(self):
        self.assertEqual(self.response.status_code, 200)
        self.assertContains(
            self.response,
            'navbar navbar-expand-lg navbar-dark bg-primary fixed-top site-navbar',
        )
        self.assertContains(self.response, '@media (max-width: 991.98px)')
        self.assertContains(
            self.response,
            '@media (min-width: 992px) and (max-width: 1399.98px)',
        )

    def test_bouton_mobile_est_accessible_et_libelles_sans_retour(self):
        self.assertContains(self.response, 'id="siteNavbarToggler"')
        self.assertContains(self.response, 'aria-controls="navbarNav"')
        self.assertContains(
            self.response,
            'aria-label="Afficher ou masquer la navigation"',
        )
        self.assertContains(self.response, 'white-space: nowrap;')

    def test_bootstrap_local_active_le_menu_sans_dependre_du_cdn(self):
        self.assertContains(
            self.response,
            'vendor/bootstrap/bootstrap.min.css',
        )
        self.assertContains(
            self.response,
            'vendor/bootstrap/bootstrap.bundle.min.js',
        )
        self.assertNotContains(
            self.response,
            'cdn.jsdelivr.net/npm/bootstrap',
        )
        self.assertContains(
            self.response,
            "menu.classList.toggle('show')",
        )

    def test_zone_tactile_et_panneau_tablette_sont_adaptes(self):
        self.assertContains(self.response, 'min-height: 44px;')
        self.assertContains(self.response, 'min-width: 44px;')
        self.assertContains(self.response, 'touch-action: manipulation;')
        self.assertContains(self.response, 'flex-basis: 100%;')
