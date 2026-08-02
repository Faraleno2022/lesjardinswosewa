from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve
from utilisateurs.models import Profil

from .models_logistique import BienEtablissement, ContributionPapierRam


TEST_MIDDLEWARE = [
    middleware for middleware in settings.MIDDLEWARE
    if middleware != 'ecole_moderne.licence_middleware.LicenceMiddleware'
]


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class LogistiqueSimplifieeTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='École Logistique', adresse='Conakry',
            telephone='+224620200001', directeur='Direction',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='Autre École', adresse='Kindia',
            telephone='+224620200002', directeur='Autre direction',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='CM1 A', niveau='PRIMAIRE_4',
            annee_scolaire='2026-2027',
        )
        self.autre_classe = Classe.objects.create(
            ecole=self.autre_ecole, nom='CM1 B', niveau='PRIMAIRE_4',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='LOG-001', prenom='Aminata', nom='Diallo', sexe='F',
            classe=self.classe, statut='ACTIF',
        )
        self.eleve_sans_contribution = Eleve.objects.create(
            matricule='LOG-002', prenom='Mamadou', nom='Camara', sexe='M',
            classe=self.classe, statut='ACTIF',
        )
        self.autre_eleve = Eleve.objects.create(
            matricule='AUT-001', prenom='Fatou', nom='Condé', sexe='F',
            classe=self.autre_classe, statut='ACTIF',
        )
        User = get_user_model()
        self.user = User.objects.create_user('logistique', password='pass12345')
        Profil.objects.update_or_create(
            user=self.user,
            defaults={
                'role': 'ADMIN', 'ecole': self.ecole,
                'telephone': '+224620200011', 'is_validated': True,
            },
        )
        self.client.force_login(self.user)

    def test_bien_calcule_disponible_et_valeur_achat(self):
        bien = BienEtablissement.objects.create(
            ecole=self.ecole, code_bien='BIEN-001', nom='Tables',
            type_bien='TABLE', quantite_achetee=20,
            quantite_utilisee=12, quantite_gatee=3,
            prix_achat_unitaire=Decimal('250000'),
        )
        self.assertEqual(bien.quantite_disponible, 5)
        self.assertEqual(bien.valeur_totale_achat, Decimal('5000000'))

    def test_bien_refuse_des_quantites_incoherentes(self):
        bien = BienEtablissement(
            ecole=self.ecole, code_bien='BIEN-002', nom='Marqueurs',
            type_bien='MARQUEUR', quantite_achetee=10,
            quantite_utilisee=8, quantite_gatee=4,
        )
        with self.assertRaises(ValidationError):
            bien.full_clean()

    def test_ajout_bien_rattache_a_ecole_et_calcule_total(self):
        response = self.client.post(reverse('depenses:creer_bien'), {
            'code_bien': '', 'nom': 'Marqueurs', 'type_bien': 'MARQUEUR',
            'marque': 'Pilot', 'quantite_achetee': 30,
            'prix_achat_unitaire': 12000, 'quantite_utilisee': 10,
            'quantite_gatee': 2, 'localisation': 'Magasin',
            'date_acquisition': '2026-08-02', 'description': '', 'observations': '',
            'ecole': self.ecole.pk,
        })
        self.assertRedirects(response, reverse('depenses:liste_biens'))
        bien = BienEtablissement.objects.get(nom='Marqueurs')
        self.assertEqual(bien.ecole, self.ecole)
        self.assertEqual(bien.quantite_disponible, 18)
        self.assertEqual(bien.valeur_acquisition, Decimal('360000'))

    def test_papier_ram_enregistre_des_paquets(self):
        response = self.client.post(reverse('depenses:ajouter_papier_ram'), {
            'eleve': self.eleve.pk,
            'annee_scolaire': '2026-2027',
            'mode_contribution': 'PAPIER',
            'nombre_paquets': 3,
            'montant_paye': 50000,
            'date_contribution': '2026-08-02',
            'observations': '',
        })
        self.assertRedirects(response, reverse('depenses:gestion_papier_ram'))
        contribution = ContributionPapierRam.objects.get(eleve=self.eleve)
        self.assertEqual(contribution.ecole, self.ecole)
        self.assertEqual(contribution.nombre_paquets, 3)
        self.assertEqual(contribution.montant_paye, Decimal('0'))

    def test_papier_ram_enregistre_un_paiement_a_la_place(self):
        response = self.client.post(reverse('depenses:ajouter_papier_ram'), {
            'eleve': self.eleve.pk,
            'annee_scolaire': '2026-2027',
            'mode_contribution': 'ARGENT',
            'nombre_paquets': 4,
            'montant_paye': 75000,
            'date_contribution': '2026-08-02',
            'observations': '',
        })
        self.assertRedirects(response, reverse('depenses:gestion_papier_ram'))
        contribution = ContributionPapierRam.objects.get(eleve=self.eleve)
        self.assertEqual(contribution.nombre_paquets, 0)
        self.assertEqual(contribution.montant_paye, Decimal('75000'))

    def test_dashboard_resume_ram_et_isole_les_ecoles(self):
        ContributionPapierRam.objects.create(
            ecole=self.ecole, eleve=self.eleve, annee_scolaire='2026-2027',
            mode_contribution='PAPIER', nombre_paquets=2,
            date_contribution=date(2026, 8, 2),
        )
        ContributionPapierRam.objects.create(
            ecole=self.autre_ecole, eleve=self.autre_eleve, annee_scolaire='2026-2027',
            mode_contribution='ARGENT', montant_paye=100000,
            date_contribution=date(2026, 8, 2),
        )
        response = self.client.get(reverse('depenses:dashboard_logistique'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['resume_ram']['total_eleves'], 2)
        self.assertEqual(response.context['resume_ram']['total_enregistres'], 1)
        self.assertEqual(response.context['resume_ram']['total_en_attente'], 1)
        self.assertEqual(response.context['resume_ram']['paquets_recus'], 2)
        self.assertNotContains(response, self.autre_eleve.matricule)

    def test_un_eleve_dune_autre_ecole_ne_peut_pas_etre_selectionne(self):
        response = self.client.get(reverse('depenses:ajouter_papier_ram'))
        self.assertContains(response, self.eleve.matricule)
        self.assertNotContains(response, self.autre_eleve.matricule)

    def test_anciennes_pages_stock_ne_sont_plus_exposees(self):
        self.assertEqual(self.client.get('/depenses/logistique/articles/').status_code, 404)
        self.assertEqual(self.client.get('/depenses/logistique/mouvements/').status_code, 404)
        self.assertEqual(self.client.get('/depenses/logistique/inventaires/').status_code, 404)
