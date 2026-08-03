from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Ecole
from utilisateurs.models import Profil

from .models_fournitures import ProduitFourniture, VenteFourniture


TEST_MIDDLEWARE = tuple(
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware != "ecole_moderne.licence_middleware.LicenceMiddleware"
)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class FournituresScolairesTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École Fournitures",
            adresse="Conakry",
            telephone="+224620300001",
            directeur="Direction",
        )
        self.autre_ecole = Ecole.objects.create(
            nom="Autre École Fournitures",
            adresse="Kindia",
            telephone="+224620300002",
            directeur="Autre direction",
        )
        User = get_user_model()
        self.user = User.objects.create_user("vendeur_fournitures", password="pass12345")
        Profil.objects.update_or_create(
            user=self.user,
            defaults={
                "role": "ADMIN",
                "ecole": self.ecole,
                "telephone": "+224620300011",
                "is_validated": True,
            },
        )
        self.client.force_login(self.user)
        self.produit = ProduitFourniture.objects.create(
            ecole=self.ecole,
            code_produit="CAH-100",
            nom="Cahier 100 pages",
            quantite_stock=20,
            prix_achat_unitaire=Decimal("1000"),
            prix_vente_unitaire=Decimal("1500"),
            seuil_alerte=3,
            cree_par=self.user,
        )

    def _vente(self, quantite=3, prix_vente=Decimal("1500")):
        return VenteFourniture.objects.create(
            produit=self.produit,
            quantite=quantite,
            prix_achat_unitaire=self.produit.prix_achat_unitaire,
            prix_vente_unitaire=prix_vente,
            date_vente=date(2026, 8, 3),
            cree_par=self.user,
        )

    def test_produit_calcule_vendu_reste_ventes_et_solde(self):
        self._vente(3, Decimal("1500"))
        self._vente(2, Decimal("1600"))

        self.assertEqual(self.produit.quantite_vendue, 5)
        self.assertEqual(self.produit.quantite_restante, 15)
        self.assertEqual(self.produit.chiffre_affaires, Decimal("7700"))
        self.assertEqual(self.produit.solde, Decimal("2700"))

    def test_creation_produit_force_ecole_utilisateur(self):
        response = self.client.post(
            reverse("depenses:creer_produit_fourniture"),
            {
                "ecole": self.autre_ecole.pk,
                "code_produit": "STY-001",
                "nom": "Stylo bleu",
                "description": "",
                "quantite_stock": 50,
                "prix_achat_unitaire": 1000,
                "prix_vente_unitaire": 1500,
                "seuil_alerte": 5,
                "actif": "on",
            },
        )

        self.assertRedirects(response, reverse("depenses:tableau_bord_fournitures"))
        produit = ProduitFourniture.objects.get(code_produit="STY-001")
        self.assertEqual(produit.ecole, self.ecole)

    def test_vente_enregistre_prix_historique_et_reduit_reste(self):
        response = self.client.post(
            reverse("depenses:enregistrer_vente_fourniture", args=[self.produit.pk]),
            {
                "quantite": 4,
                "prix_vente_unitaire": 1700,
                "date_vente": "2026-08-03",
                "acheteur": "Aminata Diallo",
                "observations": "",
            },
        )

        self.assertRedirects(response, reverse("depenses:tableau_bord_fournitures"))
        vente = VenteFourniture.objects.get()
        self.assertEqual(vente.prix_achat_unitaire, Decimal("1000"))
        self.assertEqual(vente.prix_vente_unitaire, Decimal("1700"))
        self.assertEqual(vente.montant_total, Decimal("6800"))
        self.assertEqual(vente.solde, Decimal("2800"))
        self.assertEqual(self.produit.quantite_restante, 16)

    def test_vente_refuse_stock_insuffisant(self):
        response = self.client.post(
            reverse("depenses:enregistrer_vente_fourniture", args=[self.produit.pk]),
            {
                "quantite": 21,
                "prix_vente_unitaire": 1500,
                "date_vente": "2026-08-03",
                "acheteur": "",
                "observations": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "quantite", "Stock insuffisant : 20 unité(s) disponible(s).")
        self.assertFalse(VenteFourniture.objects.exists())

    def test_dashboard_affiche_totaux_demandes(self):
        self._vente(5, Decimal("1500"))
        response = self.client.get(reverse("depenses:tableau_bord_fournitures"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["resume"]["quantite_stock"], 20)
        self.assertEqual(response.context["resume"]["quantite_vendue"], 5)
        self.assertEqual(response.context["resume"]["quantite_restante"], 15)
        self.assertEqual(response.context["resume"]["chiffre_affaires"], Decimal("7500"))
        self.assertEqual(response.context["resume"]["solde"], Decimal("2500"))
        self.assertContains(response, "Cahier 100 pages")

    def test_dashboard_et_vente_isolent_les_ecoles(self):
        autre_produit = ProduitFourniture.objects.create(
            ecole=self.autre_ecole,
            code_produit="AUT-001",
            nom="Produit autre école",
            quantite_stock=10,
            prix_achat_unitaire=1000,
            prix_vente_unitaire=1500,
        )

        dashboard = self.client.get(reverse("depenses:tableau_bord_fournitures"))
        vente = self.client.get(
            reverse("depenses:enregistrer_vente_fourniture", args=[autre_produit.pk])
        )

        self.assertNotContains(dashboard, "Produit autre école")
        self.assertEqual(vente.status_code, 404)

    def test_annulation_vente_restitue_le_stock_calcule(self):
        vente = self._vente(6)
        self.assertEqual(self.produit.quantite_restante, 14)

        response = self.client.post(
            reverse("depenses:annuler_vente_fourniture", args=[vente.pk])
        )

        self.assertRedirects(response, reverse("depenses:tableau_bord_fournitures"))
        self.assertFalse(VenteFourniture.objects.exists())
        self.assertEqual(self.produit.quantite_restante, 20)

    def test_modification_refuse_stock_inferieur_aux_ventes(self):
        self._vente(8)
        response = self.client.post(
            reverse("depenses:modifier_produit_fourniture", args=[self.produit.pk]),
            {
                "ecole": self.ecole.pk,
                "code_produit": self.produit.code_produit,
                "nom": self.produit.nom,
                "description": "",
                "quantite_stock": 5,
                "prix_achat_unitaire": 1000,
                "prix_vente_unitaire": 1500,
                "seuil_alerte": 3,
                "actif": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("quantite_stock", response.context["form"].errors)
        self.produit.refresh_from_db()
        self.assertEqual(self.produit.quantite_stock, 20)
