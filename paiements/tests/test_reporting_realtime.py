from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, Responsable
from paiements.models import (
    EcheancierPaiement,
    ModePaiement,
    Paiement,
    PaiementRemise,
    Relance,
    RemiseReduction,
    TypePaiement,
)
from utilisateurs.models import Profil
from .support import TEST_MIDDLEWARE

@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ReportingTempsReelTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="Wosewa Test", adresse="Conakry",
            telephone="+224620100001", directeur="Direction",
        )
        self.autre_ecole = Ecole.objects.create(
            nom="Autre école", adresse="Siguiri",
            telephone="+224620100002", directeur="Autre direction",
        )
        self.classe = Classe.objects.create(
            nom="CM1", ecole=self.ecole, niveau="PRIMAIRE_4",
            annee_scolaire="2025-2026",
        )
        # Une année plus récente peut être préparée sans échéancier : elle ne
        # doit pas rendre la page des soldés artificiellement vide.
        Classe.objects.create(
            nom="CM1 rentrée suivante", ecole=self.ecole, niveau="PRIMAIRE_4",
            annee_scolaire="2026-2027",
        )
        self.autre_classe = Classe.objects.create(
            nom="CM1 B", ecole=self.autre_ecole, niveau="PRIMAIRE_4",
            annee_scolaire="2025-2026",
        )
        responsable = Responsable.objects.create(
            prenom="Parent", nom="Test", relation="PERE",
            telephone="+224620100011", adresse="Conakry",
        )
        self.eleve = self._creer_eleve(
            "WOS-001", "Camara", "Aminata", self.classe, responsable
        )
        self.eleve_solde = self._creer_eleve(
            "WOS-002", "Diallo", "Mamadou", self.classe, responsable
        )
        self.autre_eleve = self._creer_eleve(
            "AUT-001", "Condé", "Fatou", self.autre_classe, responsable
        )

        self.echeancier = self._creer_echeancier(
            self.eleve, total=100000, paye=20000
        )
        self._creer_echeancier(self.eleve_solde, total=100000, paye=100000)
        self._creer_echeancier(self.autre_eleve, total=200000, paye=0)

        type_paiement = TypePaiement.objects.create(nom="Tranche 1")
        mode = ModePaiement.objects.create(nom="Espèces")
        self.paiement = Paiement.objects.create(
            eleve=self.eleve, type_paiement=type_paiement,
            mode_paiement=mode, montant=20000, statut='VALIDE',
            date_paiement=date(2026, 7, 31),
        )
        self.paiement_autre = Paiement.objects.create(
            eleve=self.autre_eleve, type_paiement=type_paiement,
            mode_paiement=mode, montant=50000, statut='VALIDE',
            date_paiement=date(2026, 7, 31),
        )
        remise = RemiseReduction.objects.create(
            nom="Remise sociale", type_remise="MONTANT_FIXE",
            valeur=10000, motif="SOCIALE",
            date_debut=date(2025, 8, 1), date_fin=date(2026, 8, 31),
        )
        PaiementRemise.objects.create(
            paiement=self.paiement, remise=remise, montant_remise=10000
        )
        self.relance = Relance.objects.create(
            eleve=self.eleve, canal="SMS", message="Rappel",
            statut="ENREGISTREE", solde_estime=70000,
        )
        Relance.objects.create(
            eleve=self.autre_eleve, canal="SMS", message="Autre rappel",
            statut="ENREGISTREE", solde_estime=150000,
        )

        User = get_user_model()
        self.comptable = User.objects.create_user(
            username="comptable_reporting", password="pass12345"
        )
        Profil.objects.update_or_create(
            user=self.comptable,
            defaults={
                'role': 'COMPTABLE', 'ecole': self.ecole,
                'telephone': "+224620100021",
                'peut_consulter_rapports': True, 'is_validated': True,
            },
        )
        self.client.force_login(self.comptable)

    def _creer_eleve(self, matricule, nom, prenom, classe, responsable):
        return Eleve.objects.create(
            nom=nom, prenom=prenom, matricule=matricule, classe=classe,
            sexe='F', date_naissance=date(2015, 1, 1),
            lieu_naissance="Conakry", date_inscription=date(2025, 9, 1),
            responsable_principal=responsable,
        )

    def _creer_echeancier(self, eleve, total, paye):
        return EcheancierPaiement.objects.create(
            eleve=eleve, annee_scolaire="2025-2026",
            frais_inscription_du=total,
            tranche_1_due=0, tranche_2_due=0, tranche_3_due=0,
            frais_inscription_paye=paye,
            tranche_1_payee=0, tranche_2_payee=0, tranche_3_payee=0,
            date_echeance_inscription=date(2025, 9, 1),
            date_echeance_tranche_1=date(2025, 10, 1),
            date_echeance_tranche_2=date(2026, 1, 1),
            date_echeance_tranche_3=date(2026, 4, 1),
        )

    @patch('paiements.views_rapport_comptable.timezone.localdate', return_value=date(2026, 8, 2))
    def test_rapport_comptable_affiche_les_donnees_recentes_de_lecole(self, _localdate):
        response = self.client.get(reverse('paiements:rapport_comptable'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['nombre_paiements'], 1)
        self.assertEqual(response.context['total_paiements'], 20000)
        self.assertContains(response, self.paiement.numero_recu)
        self.assertNotContains(response, self.paiement_autre.numero_recu)
        self.assertLessEqual(response.context['date_debut'], date(2026, 7, 31))

    def test_impayes_utilisent_echeancier_et_remise(self):
        response = self.client.get(reverse('paiements:liste_eleves_impayes'))

        self.assertEqual(response.status_code, 200)
        lignes = response.context['eleves_avec_soldes']
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['eleve'], self.eleve)
        # Une remise de tranche ne doit jamais effacer les frais d'admission.
        self.assertEqual(lignes[0]['montant_paye'], 20000)
        self.assertEqual(lignes[0]['reste_a_payer'], 80000)
        self.assertNotContains(response, self.autre_eleve.matricule)

    def test_soldes_prennent_une_annee_ayant_des_echeanciers(self):
        response = self.client.get(reverse('paiements:liste_eleves_soldes'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['annee'], '2025-2026')
        self.assertContains(response, self.eleve_solde.matricule)
        self.assertNotContains(response, self.autre_eleve.matricule)

    def test_relances_sont_filtrees_par_ecole_sans_periode_cachee(self):
        response = self.client.get(reverse('paiements:liste_relances'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.eleve.nom_complet)
        self.assertNotContains(response, self.autre_eleve.nom_complet)

    @patch('rapports.views.django_timezone.localdate', return_value=date(2026, 8, 2))
    def test_rapport_remises_ne_se_limite_pas_au_mois_courant(self, _localdate):
        response = self.client.get(reverse('rapports:rapport_remises'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['stats_remises']['total_remises'], 10000)
        self.assertContains(response, self.paiement.numero_recu)
        self.assertNotContains(response, self.paiement_autre.numero_recu)
