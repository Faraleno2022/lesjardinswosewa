from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire, Responsable
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AjoutPaiementFluxInscriptionTests(TestCase):
    """Flux d'inscription : Ajouter élève -> Ajouter paiement -> fiche du paiement
    (où une remise peut être appliquée avant validation) -> validation -> retour
    au formulaire d'inscription.

    Le paiement n'est jamais validé automatiquement : le comptable doit pouvoir
    appliquer une remise d'abord."""

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

    def test_avec_next_on_arrive_sur_la_fiche_du_paiement_sans_validation_auto(self):
        """Le paiement doit rester EN_ATTENTE et l'utilisateur atterrir sur la fiche
        du paiement, pour pouvoir appliquer une remise puis valider lui-même."""
        student = self._student("FLUX-001")
        next_url = reverse("eleves:ajouter_eleve")

        response = self._post_payment(student, next_url=next_url)

        paiement = Paiement.objects.get(eleve=student)
        self.assertEqual(paiement.statut, "EN_ATTENTE")
        self.assertIsNone(paiement.date_validation)

        detail_url = reverse("paiements:detail_paiement", args=[paiement.pk])
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(detail_url),
            f"Attendu une redirection vers {detail_url}, obtenu {response.url}",
        )
        self.assertIn("next=", response.url)

        # L'échéancier, lui, est bien créé/synchronisé dès l'ajout.
        self.assertTrue(EcheancierPaiement.objects.filter(eleve=student).exists())

    def test_la_fiche_transmet_next_au_formulaire_de_validation(self):
        student = self._student("FLUX-002")
        next_url = reverse("eleves:ajouter_eleve")
        self._post_payment(student, next_url=next_url)
        paiement = Paiement.objects.get(eleve=student)

        response = self.client.get(
            reverse("paiements:detail_paiement", args=[paiement.pk]), {"next": next_url}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["next_url"], next_url)
        self.assertContains(response, f'name="next" value="{next_url}"')

    def test_validation_renvoie_au_formulaire_d_inscription(self):
        student = self._student("FLUX-003")
        next_url = reverse("eleves:ajouter_eleve")
        self._post_payment(student, next_url=next_url)
        paiement = Paiement.objects.get(eleve=student)

        response = self.client.post(
            reverse("paiements:valider_paiement", args=[paiement.pk]),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, "VALIDE")
        self.assertEqual(paiement.valide_par, self.user)

    def test_validation_sans_next_reste_sur_la_fiche(self):
        """Comportement historique inchangé hors flux d'inscription."""
        student = self._student("FLUX-004")
        self._post_payment(student, next_url=None)
        paiement = Paiement.objects.get(eleve=student)

        response = self.client.post(
            reverse("paiements:valider_paiement", args=[paiement.pk])
        )

        self.assertRedirects(
            response, reverse("paiements:detail_paiement", args=[paiement.pk])
        )
        paiement.refresh_from_db()
        self.assertEqual(paiement.statut, "VALIDE")

    def test_sans_next_on_va_sur_l_echeancier(self):
        """Ajout de paiement classique depuis la fiche élève : comportement inchangé."""
        student = self._student("FLUX-005")

        response = self._post_payment(student, next_url=None)

        self.assertRedirects(
            response,
            reverse("paiements:echeancier_eleve", args=[student.pk]),
        )
        paiement = Paiement.objects.get(eleve=student)
        self.assertEqual(paiement.statut, "EN_ATTENTE")
