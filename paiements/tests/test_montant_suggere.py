from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement
from paiements.views import _tranches_visees_par_type, _normalize_payment_type_name

from .support import TEST_MIDDLEWARE


class TranchesViseesParTypeTests(TestCase):
    """L'analyse du libellé doit être additive : chaque tranche citée compte.
    L'ancienne cascade de `elif` faisait tomber « Inscription + Tranche 1 +
    Tranche 2 + Tranche 3 » dans la branche « + Tranche 1 + Tranche 2 » et
    oubliait donc la 3ème tranche."""

    def _tranches(self, libelle):
        return _tranches_visees_par_type(_normalize_payment_type_name(libelle))

    def test_types_simples(self):
        self.assertEqual(self._tranches("Inscription"), set())
        self.assertEqual(self._tranches("Réinscription"), set())
        self.assertEqual(self._tranches("Tranche 1"), {1})
        self.assertEqual(self._tranches("Tranche 2"), {2})
        self.assertEqual(self._tranches("Tranche 3"), {3})

    def test_types_combines(self):
        self.assertEqual(self._tranches("Inscription + Tranche 1"), {1})
        self.assertEqual(self._tranches("Inscription + Tranche 1 + Tranche 2"), {1, 2})
        self.assertEqual(
            self._tranches("Inscription + Tranche 1 + Tranche 2 + Tranche 3"), {1, 2, 3}
        )
        self.assertEqual(
            self._tranches("Réinscription + Tranche 1 + Tranche 2 + Tranche 3"), {1, 2, 3}
        )

    def test_annuel_et_scolarite_couvrent_les_trois_tranches(self):
        self.assertEqual(self._tranches("Scolarité"), {1, 2, 3})
        self.assertEqual(self._tranches("Inscription + Annuel"), {1, 2, 3})

    def test_types_hors_echeancier(self):
        self.assertEqual(self._tranches("Cantine"), set())
        self.assertEqual(self._tranches("Transport"), set())


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AjaxMontantSuggereTests(TestCase):
    """Le montant proposé doit être le reste exact à payer pour le type choisi,
    calculé sur l'échéancier à jour."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École montant suggéré",
            adresse="Conakry",
            telephone="+224620000600",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="6ème A",
            ecole=self.ecole,
            niveau="PRIMAIRE_6",
            annee_scolaire="2025-2026",
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau="PRIMAIRE_6",
            annee_scolaire="2025-2026",
            frais_inscription=Decimal("50000"),
            frais_reinscription=Decimal("30000"),
            tranche_1=Decimal("600000"),
            tranche_2=Decimal("500000"),
            tranche_3=Decimal("400000"),
        )
        self.eleve = Eleve.objects.create(
            matricule="SUGG-001",
            prenom="Test",
            nom="Suggestion",
            sexe="F",
            classe=self.classe,
            date_inscription=date(2025, 9, 1),
            statut="ACTIF",
        )
        self.user = get_user_model().objects.create_superuser(
            username="admin_sugg",
            email="admin_sugg@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

    def _demander(self, libelle_type):
        type_pmt = TypePaiement.objects.create(nom=libelle_type)
        response = self.client.get(
            reverse("paiements:ajax_montant_suggere"),
            {"eleve_id": self.eleve.pk, "type_id": type_pmt.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"), data)
        return data

    def test_inscription_seule(self):
        data = self._demander("Inscription")
        self.assertEqual(data["suggested"], 50000)
        self.assertEqual(data["breakdown"]["fi_restant"], 50000)

    def test_reinscription_utilise_le_tarif_de_reinscription(self):
        data = self._demander("Réinscription")
        self.assertEqual(data["suggested"], 30000)

    def test_inscription_plus_tranche_1(self):
        data = self._demander("Inscription + Tranche 1")
        self.assertEqual(data["suggested"], 50000 + 600000)

    def test_inscription_plus_les_trois_tranches(self):
        """Régression : la 3ème tranche était oubliée."""
        data = self._demander("Inscription + Tranche 1 + Tranche 2 + Tranche 3")
        self.assertEqual(data["suggested"], 50000 + 600000 + 500000 + 400000)

    def test_le_montant_deduit_ce_qui_est_deja_paye(self):
        from paiements.views import ensure_echeancier_for_eleve

        ech = ensure_echeancier_for_eleve(self.eleve)
        ech.tranche_1_payee = Decimal("200000")
        ech.save()

        data = self._demander("Tranche 1")

        self.assertEqual(data["suggested"], 400000)  # 600 000 - 200 000
        self.assertEqual(data["breakdown"]["t1_restant"], 400000)

    def test_type_hors_echeancier_ne_propose_rien(self):
        data = self._demander("Cantine")
        self.assertEqual(data["suggested"], 0)
        self.assertIn("aucun poste", data["breakdown"]["description"].lower())

    def test_parametres_manquants(self):
        response = self.client.get(reverse("paiements:ajax_montant_suggere"))
        self.assertEqual(response.status_code, 400)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AjaxMontantSuggereGardeProlongeeTests(TestCase):
    """Pour un élève en garde prolongée, le montant proposé doit refléter le
    forfait de scolarité, frais d'inscription en sus."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École suggestion garde",
            adresse="Conakry",
            telephone="+224620000601",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="PETITE SECTION A",
            ecole=self.ecole,
            niveau="PETITE_SECTION",
            annee_scolaire="2026-2027",
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau="PETITE_SECTION",
            annee_scolaire="2026-2027",
            frais_inscription=Decimal("50000"),
            frais_reinscription=Decimal("30000"),
            tranche_1=Decimal("1100000"),
            tranche_2=Decimal("0"),
            tranche_3=Decimal("0"),
        )
        self.eleve = Eleve.objects.create(
            matricule="SUGG-GARDE",
            prenom="Test",
            nom="Garde",
            sexe="M",
            classe=self.classe,
            date_inscription=date(2026, 9, 1),
            statut="ACTIF",
            garde_prolongee=True,
        )
        self.user = get_user_model().objects.create_superuser(
            username="admin_sugg_garde",
            email="admin_sugg_garde@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

    def _demander(self, libelle_type):
        type_pmt = TypePaiement.objects.create(nom=libelle_type)
        response = self.client.get(
            reverse("paiements:ajax_montant_suggere"),
            {"eleve_id": self.eleve.pk, "type_id": type_pmt.pk},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"), data)
        return data

    def test_reinscription_plus_annuel(self):
        """30 000 de réinscription + 2 700 000 de forfait = 2 730 000."""
        data = self._demander("Réinscription + Tranche 1 + Tranche 2 + Tranche 3")

        self.assertEqual(data["suggested"], 2730000)
        self.assertEqual(data["echeancier"]["total_du"], 2730000)

    def test_inscription_seule_ne_prend_pas_la_scolarite(self):
        data = self._demander("Inscription")

        self.assertEqual(data["suggested"], 50000)
        # La scolarité reste due à part, au montant du forfait.
        ech = data["echeancier"]
        self.assertEqual(ech["t1_du"] + ech["t2_du"] + ech["t3_du"], 2700000)
