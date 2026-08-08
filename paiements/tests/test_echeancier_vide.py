from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class EcheancierVideTests(TestCase):
    """Un échéancier peut exister mais être entièrement vide (créé avant que la
    grille tarifaire du niveau/année ne soit saisie). Tous les montants dus valent
    alors 0 et l'ajout de paiement était refusé indéfiniment avec « le reste total
    à payer pour cet élève est de 0 GNF », sans possibilité de s'en sortir."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École échéancier vide",
            adresse="Conakry",
            telephone="+224620000400",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="PETITE SECTION A",
            ecole=self.ecole,
            niveau="PETITE_SECTION",
            annee_scolaire="2026-2027",
        )
        self.type_paiement = TypePaiement.objects.create(nom="Inscription")
        self.mode_paiement = ModePaiement.objects.create(nom="Espèces")
        self.user = get_user_model().objects.create_superuser(
            username="admin_vide",
            email="admin_vide@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

        self.eleve = Eleve.objects.create(
            matricule="PSA-002",
            prenom="Djenabou",
            nom="Diallo",
            sexe="F",
            classe=self.classe,
            date_inscription=date(2026, 9, 1),
            statut="ACTIF",
        )

    def _echeancier_vide(self):
        return EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire="2026-2027",
            nature_frais="INSCRIPTION",
            frais_inscription_du=Decimal("0"),
            tranche_1_due=Decimal("0"),
            tranche_2_due=Decimal("0"),
            tranche_3_due=Decimal("0"),
            date_echeance_inscription=date(2026, 9, 1),
            date_echeance_tranche_1=date(2027, 1, 15),
            date_echeance_tranche_2=date(2027, 3, 15),
            date_echeance_tranche_3=date(2027, 5, 15),
        )

    def _grille(self):
        return GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau="PETITE_SECTION",
            annee_scolaire="2026-2027",
            frais_inscription=Decimal("50000"),
            frais_reinscription=Decimal("30000"),
            tranche_1=Decimal("1100000"),
            tranche_2=Decimal("0"),
            tranche_3=Decimal("0"),
        )

    def _post_paiement(self, montant):
        return self.client.post(
            reverse("paiements:ajouter_paiement_eleve", args=[self.eleve.pk]),
            {
                "eleve": self.eleve.pk,
                "type_paiement": self.type_paiement.pk,
                "mode_paiement": self.mode_paiement.pk,
                "montant": str(montant),
                "date_paiement": "2026-09-01",
            },
        )

    def test_echeancier_vide_est_recharge_depuis_la_grille(self):
        """Régression : l'échéancier vide doit être re-rempli depuis la grille au
        moment de l'ajout du paiement, au lieu de bloquer la saisie."""
        self._echeancier_vide()
        self._grille()

        response = self._post_paiement(50000)

        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 1)
        self.assertEqual(response.status_code, 302)

        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.frais_inscription_du, Decimal("50000"))
        self.assertEqual(ech.tranche_1_due, Decimal("1100000"))

    def test_sans_grille_le_message_indique_la_vraie_cause(self):
        """Sans grille applicable, on ne peut rien faire — mais le message doit
        désigner l'absence de grille, pas un « montant trop élevé »."""
        self._echeancier_vide()  # aucune grille créée

        response = self._post_paiement(50000)

        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 0)
        messages = [str(m) for m in response.context["messages"]]
        self.assertTrue(
            any("échéancier est vide" in m for m in messages),
            f"Message attendu absent. Messages reçus : {messages}",
        )
        self.assertTrue(
            any("Petite section" in m and "2026-2027" in m for m in messages),
            f"Le message doit citer le niveau et l'année. Messages reçus : {messages}",
        )
