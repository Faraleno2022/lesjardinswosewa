import io
import time
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from eleves.models import Classe, Ecole, Eleve
from paiements.models import EcheancierPaiement

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AdmissionListsTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='École admissions', adresse='Conakry',
            telephone='+224620200001', directeur='Direction',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='École cachée', adresse='Conakry',
            telephone='+224620200002', directeur='Direction',
        )
        self.classe = self._classe(self.ecole, '5ème A')
        self.autre_classe = self._classe(self.autre_ecole, '5ème B')
        self.user = get_user_model().objects.create_user(
            username='admissions-user', password='pass12345'
        )
        profil = self.user.profil
        profil.role = 'COMPTABLE'
        profil.ecole = self.ecole
        profil.telephone = '+224620200003'
        profil.is_validated = True
        profil.save(update_fields=['role', 'ecole', 'telephone', 'is_validated'])
        self.client.force_login(self.user)
        session = self.client.session
        session['phone_verified'] = True
        session['phone_verified_at'] = time.time()
        session.save()
        self.inscrit = self._eleve('ADM-001', 'Ibrahima', self.classe)
        self.reinscrit = self._eleve('ADM-002', 'Aïssata', self.classe)
        self.cache = self._eleve('ADM-003', 'Caché', self.autre_classe)
        self._echeancier(self.inscrit, 'INSCRIPTION', 50000, 30000)
        self._echeancier(self.reinscrit, 'REINSCRIPTION', 40000, 40000)
        self._echeancier(self.cache, 'INSCRIPTION', 999000, 999000)

    def _classe(self, ecole, nom):
        return Classe.objects.create(
            ecole=ecole, nom=nom, niveau='PRIMAIRE_5',
            annee_scolaire='2026-2027',
        )

    def _eleve(self, matricule, prenom, classe):
        return Eleve.objects.create(
            matricule=matricule, prenom=prenom, nom='Camara', sexe='F',
            classe=classe, date_inscription=date(2026, 8, 30),
        )

    def _echeancier(self, eleve, nature, du, paye):
        return EcheancierPaiement.objects.create(
            eleve=eleve, annee_scolaire='2026-2027', nature_frais=nature,
            frais_inscription_du=Decimal(str(du)),
            frais_inscription_paye=Decimal(str(paye)),
            date_echeance_inscription=date(2026, 9, 1),
            date_echeance_tranche_1=date(2026, 11, 1),
            date_echeance_tranche_2=date(2027, 1, 1),
            date_echeance_tranche_3=date(2027, 3, 1),
        )

    def test_lists_separate_admission_natures_and_schools(self):
        inscription = self.client.get(
            reverse('paiements:liste_admissions', args=['inscription'])
        )
        reinscription = self.client.get(
            reverse('paiements:liste_admissions', args=['reinscription'])
        )
        self.assertEqual(inscription.status_code, 200, getattr(inscription, 'url', ''))
        self.assertEqual(reinscription.status_code, 200, getattr(reinscription, 'url', ''))
        self.assertContains(inscription, 'ADM-001')
        self.assertNotContains(inscription, 'ADM-002')
        self.assertNotContains(inscription, 'ADM-003')
        self.assertContains(reinscription, 'ADM-002')
        self.assertNotContains(reinscription, 'ADM-001')

    def test_excel_and_pdf_exports_are_generated(self):
        excel = self.client.get(
            reverse('paiements:export_admissions_excel', args=['inscription'])
        )
        self.assertEqual(excel.status_code, 200, getattr(excel, 'url', ''))
        workbook = load_workbook(io.BytesIO(excel.content), read_only=True)
        values = list(workbook.active.values)
        self.assertTrue(any('ADM-001' in row for row in values))
        self.assertFalse(any('ADM-003' in row for row in values))

        pdf = self.client.get(
            reverse('paiements:export_admissions_pdf', args=['reinscription'])
        )
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b'%PDF'))
