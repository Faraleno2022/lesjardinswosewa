"""Le motif est obligatoire dès qu'une remise est accordée sur un paiement."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from eleves.models import Ecole, Classe, Responsable, Eleve
from paiements.models import (
    EcheancierPaiement,
    ModePaiement,
    Paiement,
    PaiementRemise,
    RemiseReduction,
    TypePaiement,
)
from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class MotifRemiseObligatoireTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pass1234"
        )
        self.client.force_login(self.user)

        self.ecole = Ecole.objects.create(
            nom="Ecole Test",
            adresse="Addr",
            telephone="+224123456789",
            email="ecole@test.com",
            directeur="Dir",
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom="7ème année",
            niveau="COLLEGE_7",
            annee_scolaire="2024-2025",
            capacite_max=40,
        )
        self.responsable = Responsable.objects.create(
            prenom="Jean",
            nom="Doe",
            relation="PERE",
            telephone="+224123456789",
            email="p@example.com",
            adresse="Addr",
        )
        self.eleve = Eleve.objects.create(
            matricule="TEMP-900",
            prenom="Alice",
            nom="Test",
            sexe="F",
            date_naissance=timezone.now().date().replace(year=timezone.now().year - 10),
            lieu_naissance="Ville",
            classe=self.classe,
            date_inscription=timezone.now().date(),
            statut="ACTIF",
            responsable_principal=self.responsable,
        )
        self.mode = ModePaiement.objects.create(nom="Espèces")
        self.type = TypePaiement.objects.create(nom="Scolarité")
        self.paiement = Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type,
            mode_paiement=self.mode,
            montant=100000,
            date_paiement=timezone.now().date(),
            statut="EN_ATTENTE",
            numero_recu="",
        )
        self.url = reverse(
            "paiements:appliquer_remise", kwargs={"paiement_id": self.paiement.id}
        )

    def _creer_remise_catalogue(self):
        today = timezone.now().date()
        return RemiseReduction.objects.create(
            nom="Remise fratrie",
            type_remise="POURCENTAGE",
            valeur=10,
            motif="FRATRIE",
            date_debut=today.replace(day=1),
            date_fin=today.replace(day=28),
            actif=True,
        )

    def test_les_sept_motifs_sont_proposes(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        for _, libelle in PaiementRemise.MOTIF_CHOICES:
            self.assertContains(resp, libelle)

    def test_remise_refusee_sans_motif(self):
        resp = self.client.post(
            self.url,
            {"montant_original": self.paiement.montant, "pourcentage_scolarite": "5"},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PaiementRemise.objects.filter(paiement=self.paiement).exists())
        self.assertIn("motif", resp.context["form"].errors)

    def test_motif_hors_liste_refuse(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "5",
                "motif": "CADEAU_MAISON",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PaiementRemise.objects.filter(paiement=self.paiement).exists())

    def test_motif_enregistre_sur_remise_pourcentage(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "5",
                "motif": "GESTE_COMMERCIAL",
                "tranches": ["1"],
                "base_calcul": "TRANCHES_DUES",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement)
        self.assertEqual(ligne.motif, "GESTE_COMMERCIAL")
        self.assertEqual(ligne.motif_libelle, "Geste commercial")
        self.assertEqual(ligne.tranches_concernees, "1")

    def test_remise_refusee_sans_tranche(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "5",
                "motif": "GESTE_COMMERCIAL",
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(PaiementRemise.objects.filter(paiement=self.paiement).exists())

    def test_motif_enregistre_sur_remise_du_catalogue(self):
        remise = self._creer_remise_catalogue()
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "remises": [remise.id],
                "motif": "PARTENAIRE",
                "tranches": ["1", "2"],
                "base_calcul": "TRANCHES_DUES",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement, remise=remise)
        self.assertEqual(ligne.motif, "PARTENAIRE")
        self.assertEqual(ligne.tranches_concernees, "1,2")

    def test_motif_precedent_repropose_en_modification(self):
        PaiementRemise.objects.create(
            paiement=self.paiement,
            remise=self._creer_remise_catalogue(),
            montant_remise=5000,
            motif="CLIENT_FIDELE",
        )
        resp = self.client.get(self.url)
        self.assertEqual(resp.context["form"].fields["motif"].initial, "CLIENT_FIDELE")

    def test_ancienne_ligne_sans_motif_reste_lisible(self):
        ligne = PaiementRemise.objects.create(
            paiement=self.paiement,
            remise=self._creer_remise_catalogue(),
            montant_remise=5000,
        )
        self.assertEqual(ligne.motif_libelle, "Non renseigné")

    def test_rapport_remises_ventile_par_motif(self):
        self.paiement.statut = "VALIDE"
        self.paiement.save(update_fields=["statut"])
        PaiementRemise.objects.create(
            paiement=self.paiement,
            remise=self._creer_remise_catalogue(),
            montant_remise=5000,
            motif="PROMOTION",
        )
        resp = self.client.get(reverse("paiements:rapport_remises"))
        self.assertEqual(resp.status_code, 200)
        motifs = {ligne["motif"]: ligne for ligne in resp.context["rows_motifs"]}
        self.assertIn("Promotion", motifs)
        self.assertEqual(motifs["Promotion"]["nb_remises"], 1)
        self.assertEqual(int(motifs["Promotion"]["total_remise"]), 5000)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RemiseBaseCalculParTrancheTests(TestCase):
    """La remise scolarité porte sur les tranches cochées, jamais sur l'inscription/réinscription."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_superuser(
            username="admin2", email="admin2@example.com", password="pass1234"
        )
        self.client.force_login(self.user)

        self.ecole = Ecole.objects.create(
            nom="Ecole Test",
            adresse="Addr",
            telephone="+224123456789",
            email="ecole@test.com",
            directeur="Dir",
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom="7ème année",
            niveau="COLLEGE_7",
            annee_scolaire="2025-2026",
            capacite_max=40,
        )
        self.responsable = Responsable.objects.create(
            prenom="Jean",
            nom="Doe",
            relation="PERE",
            telephone="+224123456789",
            email="p2@example.com",
            adresse="Addr",
        )
        self.eleve = Eleve.objects.create(
            matricule="TEMP-901",
            prenom="Ivonne",
            nom="Tounkara",
            sexe="F",
            date_naissance=timezone.now().date().replace(year=timezone.now().year - 10),
            lieu_naissance="Ville",
            classe=self.classe,
            date_inscription=timezone.now().date(),
            statut="ACTIF",
            responsable_principal=self.responsable,
        )
        today = timezone.now().date()
        self.echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire="2025-2026",
            nature_frais="REINSCRIPTION",
            frais_inscription_du=20000,
            tranche_1_due=500000,
            tranche_2_due=600000,
            tranche_3_due=400000,
            date_echeance_inscription=today,
            date_echeance_tranche_1=today,
            date_echeance_tranche_2=today,
            date_echeance_tranche_3=today,
        )
        self.mode = ModePaiement.objects.create(nom="Espèces")
        self.type = TypePaiement.objects.create(nom="Réinscription + Tranche 1")
        # Reçu combiné : 20 000 (réinscription) + 280 000 (T1 partielle) = 300 000
        self.paiement = Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type,
            mode_paiement=self.mode,
            montant=300000,
            date_paiement=today,
            statut="EN_ATTENTE",
            numero_recu="",
        )
        self.url = reverse(
            "paiements:appliquer_remise", kwargs={"paiement_id": self.paiement.id}
        )

    def test_base_tranches_dues_porte_sur_le_solde_total_de_la_tranche(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "5",
                "motif": "GESTE_COMMERCIAL",
                "tranches": ["1"],
                "base_calcul": "TRANCHES_DUES",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement)
        # 5% de 500 000 GNF (montant dû sur T1, pas la part de ce reçu) = 25 000 GNF
        self.assertEqual(int(ligne.montant_remise), 25000)
        self.assertEqual(ligne.base_calcul, "TRANCHES_DUES")

    def test_base_paiement_echeance_porte_sur_la_part_de_ce_recu(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "5",
                "motif": "GESTE_COMMERCIAL",
                "tranches": ["1"],
                "base_calcul": "PAIEMENT_ECHEANCE",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement)
        # Ce reçu ne couvre que 280 000 GNF sur T1 (300 000 - 20 000 de réinscription)
        # 5% de 280 000 GNF = 14 000 GNF
        self.assertEqual(int(ligne.montant_remise), 14000)
        self.assertEqual(ligne.base_calcul, "PAIEMENT_ECHEANCE")

    def test_remise_ignore_les_tranches_non_cochees(self):
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "pourcentage_scolarite": "10",
                "motif": "GESTE_COMMERCIAL",
                "tranches": ["1", "2"],
                "base_calcul": "TRANCHES_DUES",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement)
        # 10% de (500 000 + 600 000) = 110 000 GNF ; jamais sur les 20 000 de réinscription
        self.assertEqual(int(ligne.montant_remise), 110000)
        self.assertEqual(ligne.tranches_concernees, "1,2")

    def test_page_affiche_montant_du_et_part_de_ce_paiement(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        tranches = {t["numero"]: t for t in resp.context["tranches_info"]}
        self.assertEqual(tranches[1]["du"], 500000)
        self.assertEqual(tranches[1]["sur_ce_paiement"], 280000)
        self.assertEqual(tranches[2]["sur_ce_paiement"], 0)

    def test_plusieurs_remises_sont_plafonnees_a_la_base_selectionnee(self):
        today = timezone.now().date()
        remise_a = RemiseReduction.objects.create(
            nom='Remise fixe A', type_remise='MONTANT_FIXE', valeur=400000,
            motif='SOCIALE', date_debut=today, date_fin=today, actif=True,
        )
        remise_b = RemiseReduction.objects.create(
            nom='Remise fixe B', type_remise='MONTANT_FIXE', valeur=400000,
            motif='AUTRE', date_debut=today, date_fin=today, actif=True,
        )

        resp = self.client.post(
            self.url,
            {
                'montant_original': self.paiement.montant,
                'remises': [remise_a.id, remise_b.id],
                'motif': 'GESTE_COMMERCIAL',
                'tranches': ['1'],
                'base_calcul': 'TRANCHES_DUES',
            },
        )

        self.assertEqual(resp.status_code, 302)
        total = sum(
            ligne.montant_remise
            for ligne in PaiementRemise.objects.filter(paiement=self.paiement)
        )
        self.assertEqual(total, 500000)
