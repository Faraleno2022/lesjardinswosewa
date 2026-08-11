"""La remise ne peut jamais dépasser ce que le total dû peut encore absorber.

Cas réel : à GS Les Jardins Wosewa la grille du primaire ne comporte que deux
tranches (T3 = 0). Un reçu « Inscription + Tranche 1 + Tranche 2 » solde donc
l'année entière. L'écran de remise, qui ne lit que les paiements validés,
proposait malgré tout une base de 1 200 000 GNF avant de se faire refuser par
le contrôle final.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from eleves.models import Ecole, Classe, Responsable, Eleve
from paiements.models import (
    EcheancierPaiement,
    HistoriqueModificationPaiement,
    ModePaiement,
    Paiement,
    PaiementRemise,
    TypePaiement,
)
from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RemisePlafonneeParLesEncaissementsTests(TestCase):
    ANNEE = "2026-2027"

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin_plafond", email="admin@example.com", password="pass1234"
        )
        self.client.force_login(self.user)

        self.ecole = Ecole.objects.create(
            nom="GS LES JARDINS WOSEWA",
            adresse="Conakry",
            telephone="+224123456789",
            email="ecole@wosewa.test",
            directeur="Dir",
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom="3ÈME ANNÉE B",
            niveau="PRIMAIRE_3",
            annee_scolaire=self.ANNEE,
            capacite_max=40,
        )
        self.responsable = Responsable.objects.create(
            prenom="Sekou",
            nom="Bore",
            relation="PERE",
            telephone="+224123456789",
            email="bore@example.com",
            adresse="Conakry",
        )
        self.eleve = Eleve.objects.create(
            matricule="PN3B-901",
            prenom="Marie",
            nom="Bore",
            sexe="F",
            date_naissance=timezone.now().date().replace(year=timezone.now().year - 9),
            lieu_naissance="Conakry",
            classe=self.classe,
            date_inscription=timezone.now().date(),
            statut="ACTIF",
            responsable_principal=self.responsable,
        )
        today = timezone.now().date()
        # Grille primaire de l'école : 50 000 + 700 000 + 500 000, pas de T3.
        self.echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire=self.ANNEE,
            nature_frais="INSCRIPTION",
            frais_inscription_du=50000,
            tranche_1_due=700000,
            tranche_2_due=500000,
            tranche_3_due=0,
            date_echeance_inscription=today,
            date_echeance_tranche_1=today,
            date_echeance_tranche_2=today,
            date_echeance_tranche_3=today,
        )
        self.mode = ModePaiement.objects.create(nom="Espèces")
        self.type = TypePaiement.objects.create(
            nom="Inscription + Tranche 1 + Tranche 2"
        )

    def _creer_paiement(self, montant):
        paiement = Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type,
            mode_paiement=self.mode,
            montant=montant,
            date_paiement=timezone.now().date(),
            statut="EN_ATTENTE",
            numero_recu="",
        )
        self.url = reverse(
            "paiements:appliquer_remise", kwargs={"paiement_id": paiement.id}
        )
        return paiement

    def _poster_remise(self, paiement, pourcentage, tranches=("1", "2"), reduire=False):
        donnees = {
            "montant_original": paiement.montant,
            "pourcentage_scolarite": str(pourcentage),
            "motif": "GESTE_COMMERCIAL",
            "tranches": list(tranches),
            "base_calcul": "TRANCHES_DUES",
        }
        if reduire:
            donnees["reduire_paiement"] = "1"
        return self.client.post(self.url, donnees)

    # --- Reçu au montant brut : l'année est déjà soldée ---------------------

    def test_page_annonce_une_enveloppe_nulle_quand_le_recu_solde_l_annee(self):
        self._creer_paiement(1250000)
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context["plafond_actif"])
        self.assertEqual(resp.context["remise_max_disponible"], 0)
        self.assertEqual(resp.context["total_du_annee"], 1250000)
        self.assertEqual(resp.context["total_encaisse_annee"], 1250000)
        self.assertContains(resp, "« Déduire la remise du montant du reçu »")

    def test_formulaire_reste_disponible_pour_la_deduction(self):
        """Le reçu solde l'année, mais la déduction reste une issue possible."""
        self._creer_paiement(1250000)
        resp = self.client.get(self.url)
        self.assertContains(resp, 'id="remiseForm"')
        self.assertFalse(resp.context["annee_sur_couverte"])
        self.assertEqual(resp.context["remise_max_avec_reduction"], 1250000)

    def test_remise_refusee_sans_creer_de_ligne_a_zero(self):
        paiement = self._creer_paiement(1250000)
        resp = self._poster_remise(paiement, 10)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(
            PaiementRemise.objects.filter(paiement=paiement).exists()
        )
        messages = [str(m) for m in resp.context["messages"]]
        self.assertTrue(
            any("Déduire la remise" in message for message in messages), messages
        )

    # --- Déduction de la remise sur le reçu --------------------------------

    def test_deduction_ramene_le_recu_au_net(self):
        paiement = self._creer_paiement(1250000)
        resp = self._poster_remise(paiement, 10, reduire=True)
        self.assertEqual(resp.status_code, 302)

        ligne = PaiementRemise.objects.get(paiement=paiement)
        self.assertEqual(int(ligne.montant_remise), 120000)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)
        # Encaissement + remise couvrent le total dû, sans le dépasser.
        self.assertEqual(
            int(paiement.montant) + int(ligne.montant_remise),
            int(self.echeancier.total_du),
        )

    def test_deduction_tracee_dans_l_historique(self):
        paiement = self._creer_paiement(1250000)
        self._poster_remise(paiement, 10, reduire=True)
        historique = HistoriqueModificationPaiement.objects.filter(paiement=paiement)
        self.assertTrue(historique.exists())
        entree = historique.latest("date_modification")
        self.assertIn("montant", entree.champs_modifies)
        self.assertIn("Reçu ramené au net", entree.motif)

    def test_deduction_refusee_si_elle_annule_tout_le_recu(self):
        paiement = self._creer_paiement(1200000)
        resp = self._poster_remise(paiement, 100, reduire=True)
        self.assertEqual(resp.status_code, 302)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1200000)
        self.assertFalse(PaiementRemise.objects.filter(paiement=paiement).exists())

    def test_rejouer_la_remise_ne_deduit_pas_deux_fois(self):
        paiement = self._creer_paiement(1250000)
        self._poster_remise(paiement, 10, reduire=True)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)

        # Même écran, remise ramenée à 5 % : on repart du brut, pas du net.
        self._poster_remise(paiement, 5, reduire=True)
        paiement.refresh_from_db()
        ligne = PaiementRemise.objects.get(paiement=paiement)
        self.assertEqual(int(ligne.montant_remise), 60000)
        self.assertEqual(int(paiement.montant), 1190000)

    def test_decocher_la_deduction_restaure_le_montant_brut(self):
        # Reçu partiel : l'année garde de la marge, la remise peut donc tenir
        # sans que le reçu soit amputé.
        paiement = self._creer_paiement(600000)
        self._poster_remise(paiement, 10, reduire=True)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 480000)

        self._poster_remise(paiement, 10, reduire=False)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 600000)
        ligne = PaiementRemise.objects.get(paiement=paiement)
        self.assertEqual(int(ligne.montant_remise), 120000)
        self.assertFalse(ligne.deduite_du_paiement)

    def test_decocher_sans_marge_refuse_et_ne_touche_a_rien(self):
        """Quand le brut solde l'année, décocher n'a pas de sens : on refuse.

        Restaurer le brut tout en gardant la remise créerait le trop-perçu que
        la déduction évitait. Pour revenir en arrière il faut annuler la remise.
        """
        paiement = self._creer_paiement(1250000)
        self._poster_remise(paiement, 10, reduire=True)

        resp = self._poster_remise(paiement, 10, reduire=False)
        self.assertEqual(resp.status_code, 200)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)
        ligne = PaiementRemise.objects.get(paiement=paiement)
        self.assertEqual(int(ligne.montant_remise), 120000)
        self.assertTrue(ligne.deduite_du_paiement)

    def test_case_prcochee_en_reedition(self):
        paiement = self._creer_paiement(1250000)
        self._poster_remise(paiement, 10, reduire=True)
        resp = self.client.get(self.url)
        self.assertTrue(resp.context["form"].fields["reduire_paiement"].initial)

    def test_annuler_une_remise_deduite_rend_le_montant_au_recu(self):
        paiement = self._creer_paiement(1250000)
        self._poster_remise(paiement, 10, reduire=True)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)

        self.client.post(
            reverse("paiements:annuler_remise_paiement", args=[paiement.id])
        )
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1250000)
        self.assertFalse(PaiementRemise.objects.filter(paiement=paiement).exists())

    def test_annuler_une_remise_non_deduite_laisse_le_recu_intact(self):
        paiement = self._creer_paiement(1130000)
        self._poster_remise(paiement, 10, reduire=False)
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)

        self.client.post(
            reverse("paiements:annuler_remise_paiement", args=[paiement.id])
        )
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1130000)

    def test_annee_sur_couverte_bloque_meme_la_deduction(self):
        paiement = self._creer_paiement(1250000)
        # Un second encaissement fait passer le total au-dessus du dû.
        Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type,
            mode_paiement=self.mode,
            montant=50000,
            date_paiement=timezone.now().date(),
            statut="EN_ATTENTE",
            numero_recu="",
        )
        resp = self.client.get(self.url)
        self.assertTrue(resp.context["annee_sur_couverte"])
        self.assertNotContains(resp, 'id="remiseForm"')

        resp = self._poster_remise(paiement, 10, reduire=True)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PaiementRemise.objects.filter(paiement=paiement).exists())
        paiement.refresh_from_db()
        self.assertEqual(int(paiement.montant), 1250000)

    # --- Reçu saisi au net : la remise passe -------------------------------

    def test_recu_saisi_au_net_laisse_passer_la_remise(self):
        paiement = self._creer_paiement(1130000)
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["remise_max_disponible"], 120000)

        resp = self._poster_remise(paiement, 10)
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=paiement)
        # 10 % de (700 000 + 500 000) = 120 000, soit exactement l'enveloppe.
        self.assertEqual(int(ligne.montant_remise), 120000)

    def test_remise_excedentaire_est_ramenee_a_l_enveloppe(self):
        paiement = self._creer_paiement(1130000)
        resp = self._poster_remise(paiement, 50)
        self.assertEqual(resp.status_code, 302)
        total = sum(
            ligne.montant_remise
            for ligne in PaiementRemise.objects.filter(paiement=paiement)
        )
        # 50 % de 1 200 000 = 600 000, plafonnés aux 120 000 encore absorbables.
        self.assertEqual(int(total), 120000)
        self.assertEqual(
            int(self.echeancier.total_du),
            int(paiement.montant) + int(total),
        )

    def test_remises_des_autres_paiements_reduisent_l_enveloppe(self):
        premier = self._creer_paiement(1010000)
        self._poster_remise(premier, 10)  # 120 000 de remise sur le premier reçu

        second = self._creer_paiement(100000)
        resp = self.client.get(self.url)
        # 1 250 000 - (1 010 000 + 100 000) - 120 000 = 20 000
        self.assertEqual(resp.context["remise_max_disponible"], 20000)

        self._poster_remise(second, 10)
        total = sum(
            ligne.montant_remise
            for ligne in PaiementRemise.objects.filter(paiement=second)
        )
        self.assertEqual(int(total), 20000)
