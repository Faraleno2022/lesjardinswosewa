"""Un montant supérieur au type sélectionné doit être confirmé explicitement.

Les contrôles anti-sur-paiement par type sont neutralisés par
``allow_sequential_overflow`` et le plafond annuel laisse évidemment passer un
reçu qui solde l'année. Sans cette confirmation, un « Réinscription + Tranche 1 »
saisi trop haut couvre toute la scolarité sans que le caissier le voie.
"""

from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire, Responsable
from paiements.models import ModePaiement, Paiement, TypePaiement

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class MontantSuperieurAuTypeTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École excédent",
            adresse="Conakry",
            telephone="+224620000300",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="3ème année",
            ecole=self.ecole,
            niveau="PRIMAIRE_3",
            annee_scolaire="2025-2026",
        )
        self.responsable = Responsable.objects.create(
            prenom="Parent",
            nom="Excedent",
            relation="PERE",
            telephone="+224620000301",
            adresse="Conakry",
        )
        # 30 000 de réinscription + 700 000 + 500 000, pas de 3ème tranche.
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau=self.classe.niveau,
            annee_scolaire=self.classe.annee_scolaire,
            frais_inscription=Decimal("50000"),
            frais_reinscription=Decimal("30000"),
            tranche_1=Decimal("700000"),
            tranche_2=Decimal("500000"),
            tranche_3=Decimal("0"),
        )
        self.type_reinsc_t1 = TypePaiement.objects.create(
            nom="Réinscription + Tranche 1"
        )
        self.mode = ModePaiement.objects.create(nom="Espèces")
        self.user = get_user_model().objects.create_superuser(
            username="admin_excedent",
            email="admin_excedent@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

        self.eleve = Eleve.objects.create(
            nom="Bah",
            prenom="Fatou",
            matricule="EXC-001",
            classe=self.classe,
            sexe="F",
            date_naissance=date(2016, 1, 1),
            lieu_naissance="Conakry",
            date_inscription=date(2025, 9, 1),
            responsable_principal=self.responsable,
        )

    def _poster(self, montant, confirmer=False):
        url = reverse("paiements:ajouter_paiement_eleve", args=[self.eleve.pk])
        donnees = {
            "eleve": self.eleve.pk,
            "type_paiement": self.type_reinsc_t1.pk,
            "mode_paiement": self.mode.pk,
            "montant": str(montant),
            "date_paiement": "2025-09-01",
        }
        if confirmer:
            donnees["confirmation_paiement_excedent"] = "1"
        return self.client.post(url, donnees)

    def test_montant_exact_passe_sans_confirmation(self):
        # 30 000 (réinscription) + 700 000 (T1)
        resp = self._poster(730000)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 1)

    def test_montant_superieur_demande_confirmation(self):
        # Le reçu couvrirait aussi la T2 : 30 000 + 700 000 + 500 000
        resp = self._poster(1230000)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Paiement.objects.filter(eleve=self.eleve).exists())
        self.assertTrue(resp.context["show_excess_confirmation"])
        self.assertEqual(resp.context["excedent"], 500000)

    def test_repartition_annoncee_avant_confirmation(self):
        resp = self._poster(1230000)
        repartition = {
            ligne["libelle"]: ligne["montant"]
            for ligne in resp.context["repartition_excedent"]
        }
        self.assertEqual(repartition["Frais de réinscription"], 30000)
        self.assertEqual(repartition["1ère tranche"], 700000)
        self.assertEqual(repartition["2ème tranche"], 500000)

    def test_montant_superieur_accepte_apres_confirmation(self):
        resp = self._poster(1230000, confirmer=True)
        self.assertEqual(resp.status_code, 302)
        paiement = Paiement.objects.get(eleve=self.eleve)
        self.assertEqual(int(paiement.montant), 1230000)

    def test_montant_inferieur_garde_sa_propre_confirmation(self):
        """Le contrôle du paiement partiel n'est pas remplacé par celui-ci."""
        resp = self._poster(500000)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Paiement.objects.filter(eleve=self.eleve).exists())
        self.assertTrue(resp.context.get("show_partial_confirmation"))
        self.assertIsNone(resp.context.get("show_excess_confirmation"))
