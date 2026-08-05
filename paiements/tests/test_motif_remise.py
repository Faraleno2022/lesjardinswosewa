"""Le motif est obligatoire dès qu'une remise est accordée sur un paiement."""

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from eleves.models import Ecole, Classe, Responsable, Eleve
from paiements.models import (
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
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement)
        self.assertEqual(ligne.motif, "GESTE_COMMERCIAL")
        self.assertEqual(ligne.motif_libelle, "Geste commercial")

    def test_motif_enregistre_sur_remise_du_catalogue(self):
        remise = self._creer_remise_catalogue()
        resp = self.client.post(
            self.url,
            {
                "montant_original": self.paiement.montant,
                "remises": [remise.id],
                "motif": "PARTENAIRE",
            },
        )
        self.assertEqual(resp.status_code, 302)
        ligne = PaiementRemise.objects.get(paiement=self.paiement, remise=remise)
        self.assertEqual(ligne.motif, "PARTENAIRE")

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
