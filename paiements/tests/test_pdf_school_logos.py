from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class PaiementsPdfSchoolLogoTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='pdf-logo',
            email='pdf-logo@example.com',
            password='mot-de-passe-test',
        )
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(
            nom='Ecole du logo PDF',
            adresse='Conakry',
            telephone='+224620000801',
            directeur='Direction',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='Classe logo',
            niveau='LYCEE_11',
            annee_scolaire='2025-2026',
        )

    @patch('paiements.export_paiements_filtres._draw_header_and_watermark')
    def test_liste_filtree_transmet_ecole_a_entete_pdf(self, draw_header):
        response = self.client.get(
            reverse('paiements:export_paiements_filtres_pdf'),
            {'classe_id': self.classe.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreaterEqual(draw_header.call_count, 1)
        self.assertEqual(draw_header.call_args.kwargs['ecole'], self.ecole)

    @patch('paiements.views_tranches._draw_header_and_watermark')
    def test_tranches_transmet_ecole_a_entete_pdf(self, draw_header):
        response = self.client.get(
            reverse('paiements:export_tranches_par_classe_pdf'),
            {'classe': self.classe.pk, 'annee_scolaire': '2025-2026'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertGreaterEqual(draw_header.call_count, 1)
        self.assertEqual(draw_header.call_args.kwargs['ecole'], self.ecole)

    @patch('reportlab.pdfgen.canvas.Canvas.drawImage')
    @patch(
        'paiements.rapports_professionnels._get_logo_path',
        return_value='logo-ecole-test.png',
    )
    def test_rapport_comptable_ajoute_logo_et_filigrane(
        self, get_logo_path, draw_image,
    ):
        response = self.client.get(
            reverse('paiements:export_comptabilite_pdf'),
            {'classe_id': self.classe.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        get_logo_path.assert_called_once_with(self.ecole)
        self.assertGreaterEqual(draw_image.call_count, 2)

    @patch('reportlab.pdfgen.canvas.Canvas.drawImage')
    @patch(
        'paiements.rapports_professionnels._get_logo_path',
        return_value='logo-ecole-test.png',
    )
    def test_export_modes_ajoute_logo_et_filigrane(
        self, get_logo_path, draw_image,
    ):
        response = self.client.get(
            reverse('paiements:export_modes_encaissement_pdf'),
            {'classe_id': self.classe.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        get_logo_path.assert_called_once_with(self.ecole)
        self.assertGreaterEqual(draw_image.call_count, 2)
