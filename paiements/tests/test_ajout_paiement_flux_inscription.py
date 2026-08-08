from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire, Responsable
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement
from utilisateurs.models import Profil

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AjoutPaiementFluxInscriptionTests(TestCase):
    """Vérifie l'enchaînement : ajout paiement -> validation automatique de
    l'échéancier et du paiement -> retour au formulaire d'inscription, lorsque
    `next` est fourni (flux "nouvel élève")."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École flux inscription",
            adresse="Conakry",
            telephone="+224620000200",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="6ème B",
            ecole=self.ecole,
            niveau="PRIMAIRE_6",
            annee_scolaire="2025-2026",
        )
        self.responsable = Responsable.objects.create(
            prenom="Parent",
            nom="Flux",
            relation="PERE",
            telephone="+224620000201",
            adresse="Conakry",
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau=self.classe.niveau,
            annee_scolaire=self.classe.annee_scolaire,
            frais_inscription=Decimal("30000"),
            frais_reinscription=Decimal("20000"),
            tranche_1=Decimal("100000"),
            tranche_2=Decimal("100000"),
            tranche_3=Decimal("100000"),
        )
        self.type_paiement = TypePaiement.objects.create(nom="Inscription")
        self.mode_paiement = ModePaiement.objects.create(nom="Espèces")
        self.user = get_user_model().objects.create_superuser(
            username="admin_flux",
            email="admin_flux@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

    def _student(self, matricule):
        return Eleve.objects.create(
            nom="Diallo",
            prenom="Test",
            matricule=matricule,
            classe=self.classe,
            sexe="M",
            date_naissance=date(2015, 1, 1),
            lieu_naissance="Conakry",
            date_inscription=date(2025, 9, 1),
            responsable_principal=self.responsable,
        )

    def _post_payment(self, student, *, next_url=None, montant="30000"):
        url = reverse("paiements:ajouter_paiement_eleve", args=[student.pk])
        data = {
            "eleve": student.pk,
            "type_paiement": self.type_paiement.pk,
            "mode_paiement": self.mode_paiement.pk,
            "montant": montant,
            "date_paiement": "2025-09-01",
        }
        if next_url:
            data["next"] = next_url
        return self.client.post(url, data)

    def test_avec_next_le_paiement_est_valide_automatiquement_et_retourne_a_inscription(self):
        student = self._student("FLUX-001")
        next_url = reverse("eleves:ajouter_eleve")

        response = self._post_payment(student, next_url=next_url)

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

        paiement = Paiement.objects.get(eleve=student)
        self.assertEqual(paiement.statut, "VALIDE")
        self.assertEqual(paiement.valide_par, self.user)
        self.assertIsNotNone(paiement.date_validation)

        echeancier = EcheancierPaiement.objects.get(eleve=student)
        self.assertEqual(echeancier.frais_inscription_paye, Decimal("30000"))

    def test_sans_next_le_paiement_reste_en_attente(self):
        student = self._student("FLUX-002")

        response = self._post_payment(student, next_url=None)

        self.assertRedirects(
            response,
            reverse("paiements:echeancier_eleve", args=[student.pk]),
        )

        paiement = Paiement.objects.get(eleve=student)
        self.assertEqual(paiement.statut, "EN_ATTENTE")
        self.assertIsNone(paiement.date_validation)

        echeancier = EcheancierPaiement.objects.get(eleve=student)
        self.assertEqual(echeancier.frais_inscription_paye, Decimal("0"))

    def test_avec_next_mais_sans_permission_le_paiement_reste_en_attente(self):
        # Une secrétaire (rôle sans droit de validation implicite, contrairement au
        # rôle COMPTABLE) peut saisir un paiement mais pas le valider automatiquement.
        secretaire = get_user_model().objects.create_user(
            username="secretaire_sans_droit",
            email="secretaire_sans_droit@example.com",
            password="pass12345",
        )
        Profil.objects.update_or_create(
            user=secretaire,
            defaults=dict(
                role="SECRETAIRE",
                ecole=self.ecole,
                is_validated=True,
                actif=True,
                peut_ajouter_paiements=True,
                peut_valider_paiements=False,
            ),
        )
        self.client.force_login(secretaire)

        student = self._student("FLUX-003")
        next_url = reverse("eleves:ajouter_eleve")

        response = self._post_payment(student, next_url=next_url)

        self.assertRedirects(response, next_url, fetch_redirect_response=False)

        paiement = Paiement.objects.get(eleve=student)
        self.assertEqual(paiement.statut, "EN_ATTENTE")
        self.assertIsNone(paiement.valide_par)
