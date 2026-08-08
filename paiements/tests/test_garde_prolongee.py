from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire
from paiements.models import EcheancierPaiement
from paiements.views import ensure_echeancier_for_eleve

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class GardeProlongeeTarificationTests(TestCase):
    """Le forfait de garde prolongée (2 700 000 maternelle/garderie, 2 800 000
    primaire, 2 850 000 collège 10ème) est un montant GLOBAL : les frais
    d'inscription/réinscription ne doivent jamais être ignorés, ni ajoutés en
    plus du forfait — ils doivent en être déduits avant répartition en tranches.
    Ce comportement doit se retrouver partout où l'échéancier est initialisé."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École garde prolongée",
            adresse="Conakry",
            telephone="+224620000300",
            directeur="Direction",
        )
        self.user = get_user_model().objects.create_superuser(
            username="admin_garde",
            email="admin_garde@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

    def _classe_et_grille(self, niveau, frais_inscription, frais_reinscription):
        classe = Classe.objects.create(
            nom=f"Classe {niveau}",
            ecole=self.ecole,
            niveau=niveau,
            annee_scolaire="2025-2026",
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau=niveau,
            annee_scolaire="2025-2026",
            frais_inscription=Decimal(str(frais_inscription)),
            frais_reinscription=Decimal(str(frais_reinscription)),
            tranche_1=Decimal("700000"),
            tranche_2=Decimal("600000"),
            tranche_3=Decimal("500000"),
        )
        return classe

    def _eleve(self, classe, matricule):
        return Eleve.objects.create(
            matricule=matricule,
            prenom="Test",
            nom="Garde",
            sexe="M",
            classe=classe,
            date_inscription=date(2025, 9, 1),
            statut="ACTIF",
            garde_prolongee=True,
        )

    def test_echeancier_maternelle_inscription(self):
        classe = self._classe_et_grille("GRANDE_SECTION", 50000, 30000)
        eleve = self._eleve(classe, "GARDE-001")

        ech = ensure_echeancier_for_eleve(eleve, prefer_reinscription=False)

        self.assertEqual(ech.frais_inscription_du, Decimal("50000"))
        total = ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due
        self.assertEqual(total, Decimal("2700000"))

    def test_echeancier_maternelle_reinscription(self):
        classe = self._classe_et_grille("CRECHE", 50000, 30000)
        eleve = self._eleve(classe, "GARDE-002")

        ech = ensure_echeancier_for_eleve(eleve, prefer_reinscription=True)

        self.assertEqual(ech.frais_inscription_du, Decimal("30000"))
        total = ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due
        self.assertEqual(total, Decimal("2700000"))

    def test_echeancier_primaire_reinscription(self):
        classe = self._classe_et_grille("PRIMAIRE_4", 50000, 30000)
        eleve = self._eleve(classe, "GARDE-003")

        ech = ensure_echeancier_for_eleve(eleve, prefer_reinscription=True)

        self.assertEqual(ech.frais_inscription_du, Decimal("30000"))
        total = ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due
        self.assertEqual(total, Decimal("2800000"))

    def test_echeancier_college_10_inscription(self):
        classe = self._classe_et_grille("COLLEGE_10", 70000, 50000)
        eleve = self._eleve(classe, "GARDE-004")

        ech = ensure_echeancier_for_eleve(eleve, prefer_reinscription=False)

        self.assertEqual(ech.frais_inscription_du, Decimal("70000"))
        total = ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due
        self.assertEqual(total, Decimal("2850000"))

    def test_college_9_non_concerne_par_le_forfait(self):
        classe = self._classe_et_grille("COLLEGE_9", 70000, 50000)
        eleve = self._eleve(classe, "GARDE-005")

        ech = ensure_echeancier_for_eleve(eleve, prefer_reinscription=False)

        total = ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due
        # Grille normale (frais d'inscription + 3 tranches), pas de forfait.
        self.assertEqual(total, Decimal("70000") + Decimal("700000") + Decimal("600000") + Decimal("500000"))

    def test_formulaire_creation_manuelle_echeancier_applique_le_forfait(self):
        """Régression : l'écran de création manuelle d'échéancier
        (paiements:creer_echeancier) pré-remplissait les tranches depuis la
        grille tarifaire brute, sans jamais appliquer le forfait de garde
        prolongée."""
        classe = self._classe_et_grille("PRIMAIRE_2", 50000, 30000)
        eleve = self._eleve(classe, "GARDE-006")
        self.assertIsNone(EcheancierPaiement.objects.filter(eleve=eleve).first())

        response = self.client.get(reverse("paiements:creer_echeancier", args=[eleve.pk]))

        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        total = (
            form.initial["frais_inscription_du"]
            + form.initial["tranche_1_due"]
            + form.initial["tranche_2_due"]
            + form.initial["tranche_3_due"]
        )
        self.assertEqual(total, Decimal("2800000"))
