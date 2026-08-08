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


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class GardeProlongeeAlignementFraisTests(TestCase):
    """Le forfait est un montant GLOBAL. Quand `_align_enrollment_fee` ajuste le
    frais d'inscription/réinscription (par exemple parce que la grille devient
    enfin trouvable après correction du niveau de la classe), les tranches
    doivent être rééquilibrées pour que le total reste égal au forfait."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École alignement forfait",
            adresse="Conakry",
            telephone="+224620000500",
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
            matricule="PSA-001",
            prenom="Fara",
            nom="Leno",
            sexe="M",
            classe=self.classe,
            date_inscription=date(2026, 9, 1),
            statut="ACTIF",
            garde_prolongee=True,
        )

    def test_le_total_reste_egal_au_forfait_apres_alignement_du_frais(self):
        from paiements.views import _align_enrollment_fee

        # Échéancier tel que construit quand aucune grille n'était trouvable :
        # frais à 0 et forfait réparti également sur les 3 tranches.
        ech = EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire="2026-2027",
            nature_frais="INSCRIPTION",
            frais_inscription_du=Decimal("0"),
            tranche_1_due=Decimal("900000"),
            tranche_2_due=Decimal("900000"),
            tranche_3_due=Decimal("900000"),
            date_echeance_inscription=date(2026, 9, 1),
            date_echeance_tranche_1=date(2027, 1, 15),
            date_echeance_tranche_2=date(2027, 3, 15),
            date_echeance_tranche_3=date(2027, 5, 15),
        )
        self.assertEqual(
            ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due,
            Decimal("2700000"),
        )

        _align_enrollment_fee(self.eleve, ech, "Réinscription + Tranche 1")
        ech.refresh_from_db()

        # Le frais de réinscription est désormais pris en compte...
        self.assertEqual(ech.frais_inscription_du, Decimal("30000"))
        # ...sans que le total global ne dépasse le forfait.
        total = (
            ech.frais_inscription_du + ech.tranche_1_due
            + ech.tranche_2_due + ech.tranche_3_due
        )
        self.assertEqual(total, Decimal("2700000"))

    def test_total_deja_derive_est_repare_meme_sans_changement_de_frais(self):
        """Cas du reçu REC20260010 (SUZANNE LENO) : l'échéancier avait été créé
        au tarif d'inscription (50 000 + 2 650 000), puis le frais avait été
        aligné sur la réinscription (30 000) sans toucher aux tranches — d'où un
        total de 2 680 000 au lieu de 2 700 000. Le frais étant désormais déjà
        correct, seule une réparation inconditionnelle peut rattraper l'écart."""
        from paiements.views import _align_enrollment_fee

        ech = EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire="2026-2027",
            nature_frais="REINSCRIPTION",
            frais_inscription_du=Decimal("30000"),   # déjà aligné
            tranche_1_due=Decimal("2650000"),        # calculée pour un frais de 50 000
            tranche_2_due=Decimal("0"),
            tranche_3_due=Decimal("0"),
            date_echeance_inscription=date(2026, 7, 1),
            date_echeance_tranche_1=date(2026, 10, 1),
            date_echeance_tranche_2=date(2027, 1, 1),
            date_echeance_tranche_3=date(2027, 4, 1),
        )
        self.assertEqual(
            ech.frais_inscription_du + ech.tranche_1_due + ech.tranche_2_due + ech.tranche_3_due,
            Decimal("2680000"),
        )

        _align_enrollment_fee(self.eleve, ech, "Réinscription + Tranche 1")
        ech.refresh_from_db()

        self.assertEqual(ech.frais_inscription_du, Decimal("30000"))
        total = (
            ech.frais_inscription_du + ech.tranche_1_due
            + ech.tranche_2_due + ech.tranche_3_due
        )
        self.assertEqual(total, Decimal("2700000"))
