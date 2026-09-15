import io
from datetime import date

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from .models import Classe, Ecole, Eleve


TEST_MIDDLEWARE = tuple(
    middleware for middleware in settings.MIDDLEWARE
    if middleware != 'ecole_moderne.licence_middleware.LicenceMiddleware'
)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestAccueilElevesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='test-accueil-admin', email='admin@example.com',
            password='pass12345',
        )
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(
            nom='École accueil', adresse='Conakry',
            telephone='+224620300001', directeur='Direction', etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='1ère A', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        self.ancien = self._eleve('ACC-001', 'Ancien', False)
        self.recent = self._eleve('ACC-002', 'Récent', True)

    def _eleve(self, matricule, prenom, evalue):
        return Eleve.objects.create(
            matricule=matricule, prenom=prenom, nom='Diallo', sexe='M',
            classe=self.classe, date_inscription=date(2026, 8, 30),
            test_accueil_evalue=evalue,
        )

    def test_recent_student_is_listed_first_and_can_be_toggled(self):
        response = self.client.get(reverse('eleves:liste_eleves'))
        content = response.content.decode()
        self.assertLess(content.index('ACC-002'), content.index('ACC-001'))

        toggle = self.client.post(
            reverse('eleves:pointer_test_accueil', args=[self.ancien.id]),
            {'next': '/eleves/?partial=1&test_accueil=non-evalue'},
        )
        self.assertEqual(toggle.status_code, 302)
        self.assertEqual(toggle.url, '/eleves/?test_accueil=non-evalue')
        self.ancien.refresh_from_db()
        self.assertTrue(self.ancien.test_accueil_evalue)

    def test_filter_and_exports_separate_evaluated_students(self):
        response = self.client.get(
            reverse('eleves:liste_eleves'), {'test_accueil': 'non-evalue'}
        )
        self.assertContains(response, 'ACC-001')
        self.assertNotContains(response, 'ACC-002')

        excel = self.client.get(
            reverse('eleves:export_test_accueil_excel', args=['evalues'])
        )
        workbook = load_workbook(io.BytesIO(excel.content), read_only=True)
        values = list(workbook.active.values)
        self.assertTrue(any('ACC-002' in row for row in values))
        self.assertFalse(any('ACC-001' in row for row in values))

        pdf = self.client.get(
            reverse('eleves:export_test_accueil_pdf', args=['non-evalues'])
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
