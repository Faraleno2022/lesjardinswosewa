from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from eleves.models import Ecole
from .models import Enseignant, PeriodeSalaire, TypeEnseignant
from .services import calculer_etat_salaire
from .tests import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class PersonnelEtPrimesTests(TestCase):
    types = (
        TypeEnseignant.CHAUFFEUR, TypeEnseignant.VIGILE,
        TypeEnseignant.ENTRETIEN, TypeEnseignant.NOUNOU,
        TypeEnseignant.RESTAURATION,
    )

    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='personnel-primes', password='test', email='test@example.com',
        )
        self.ecole = Ecole.objects.create(
            nom='Personnel test', adresse='Conakry', telephone='620000001',
            directeur='Direction', etat='VALIDE',
        )
        self.user.profil.ecole = self.ecole
        self.user.profil.save()
        self.periode = PeriodeSalaire.objects.create(
            ecole=self.ecole, mois=9, annee=2026, cree_par=self.user,
        )
        self.client.force_login(self.user)

    def test_creation_cinq_categories_et_filtre(self):
        page = self.client.get(reverse('salaires:ajouter_enseignant'))
        self.assertEqual(page.status_code, 200)
        for code in self.types:
            with self.subTest(type=code):
                self.assertContains(page, code.label)
                response = self.client.post(reverse('salaires:ajouter_enseignant'), {
                    'nom': code, 'prenoms': 'Test', 'ecole': self.ecole.pk,
                    'type_enseignant': code, 'statut': 'ACTIF',
                    'salaire_fixe': '1000000', 'date_embauche': '2026-09-01',
                })
                self.assertEqual(response.status_code, 302)
                travailleur = Enseignant.objects.get(nom=code)
                self.assertTrue(travailleur.est_salaire_fixe)
                self.assertEqual(travailleur.calculer_salaire_mensuel(), Decimal('1000000'))
                self.assertFalse(travailleur.affectations.exists())
                listing = self.client.get(reverse('salaires:liste_enseignants'), {'type_enseignant': code})
                self.assertContains(listing, travailleur.nom_complet)
                self.assertContains(listing, code.label)

    def test_primes_net_recalcul_et_acces_depuis_fiche(self):
        for code in self.types:
            with self.subTest(type=code):
                travailleur = Enseignant.objects.create(
                    nom=code, prenoms='Test', ecole=self.ecole,
                    type_enseignant=code, salaire_fixe=1000000,
                    date_embauche=date(2026, 9, 1), cree_par=self.user,
                )
                etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
                self.assertEqual(etat.salaire_base, Decimal('1000000'))
                detail = self.client.get(reverse('salaires:detail_enseignant', args=[travailleur.pk]))
                self.assertContains(detail, 'Primes et retenues')
                response = self.client.post(reverse('salaires:ajuster_etat_salaire', args=[etat.pk]), {
                    'salaire_base': '1000000', 'prime_exceptionnelle': '150000',
                    'deductions': '25000', 'observations': 'Prime de rendement',
                })
                self.assertEqual(response.status_code, 302)
                etat.refresh_from_db()
                self.assertEqual(etat.salaire_net, Decimal('1125000'))
                etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
                self.assertEqual(etat.primes, Decimal('150000'))
                self.assertEqual(etat.salaire_net, Decimal('1125000'))
                detail = self.client.get(reverse('salaires:detail_enseignant', args=[travailleur.pk]))
                self.assertContains(detail, 'Primes :')
                pdf = self.client.get(reverse('salaires:fiche_paie_pdf', args=[etat.pk]))
                self.assertEqual(pdf.status_code, 200)
                texte = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
                self.assertIn('Primes', texte)
                self.assertIn('150 000', texte)
                self.assertIn('1 125 000', texte)

    def test_salaire_fixe_obligatoire_pour_chaque_categorie(self):
        for code in self.types:
            with self.subTest(type=code), self.assertRaises(ValidationError):
                Enseignant.objects.create(
                    nom=code, prenoms='Test', ecole=self.ecole,
                    type_enseignant=code, date_embauche=date(2026, 9, 1), cree_par=self.user,
                )
