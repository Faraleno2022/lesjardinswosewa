"""Gestion du stock et des ventes de fournitures scolaires."""

from decimal import Decimal
from uuid import uuid4

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from synchronisation.mixins import SyncTrackedModel


MONEY_FIELD = DecimalField(max_digits=15, decimal_places=0)


class ProduitFourniture(SyncTrackedModel):
    """Produit proposé à la vente par une école."""

    ecole = models.ForeignKey(
        "eleves.Ecole",
        on_delete=models.CASCADE,
        related_name="produits_fournitures",
        verbose_name="École",
    )
    code_produit = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Code produit",
    )
    nom = models.CharField(max_length=200, verbose_name="Produit")
    description = models.TextField(blank=True, verbose_name="Description")
    quantite_stock = models.PositiveIntegerField(
        default=0,
        verbose_name="Quantité mise en stock",
    )
    prix_achat_unitaire = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=Decimal("0"),
        verbose_name="Prix d'achat unitaire (GNF)",
    )
    prix_vente_unitaire = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=Decimal("0"),
        verbose_name="Prix de vente unitaire (GNF)",
    )
    seuil_alerte = models.PositiveIntegerField(
        default=5,
        verbose_name="Seuil d'alerte",
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="produits_fournitures_crees",
        verbose_name="Créé par",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produit de fourniture scolaire"
        verbose_name_plural = "Produits de fournitures scolaires"
        ordering = ["nom", "code_produit"]
        constraints = [
            models.UniqueConstraint(
                fields=["ecole", "code_produit"],
                name="unique_produit_fourniture_ecole_code",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_achat_unitaire__gte=0),
                name="produit_fourniture_prix_achat_positif",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_vente_unitaire__gte=0),
                name="produit_fourniture_prix_vente_positif",
            ),
        ]

    def __str__(self):
        return f"{self.code_produit} - {self.nom}"

    def save(self, *args, **kwargs):
        if not self.code_produit:
            self.code_produit = f"FOUR-{uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.pk and self.quantite_stock < self.quantite_vendue:
            raise ValidationError(
                {
                    "quantite_stock": (
                        "La quantité en stock ne peut pas être inférieure à "
                        f"la quantité déjà vendue ({self.quantite_vendue})."
                    )
                }
            )

    @property
    def quantite_vendue(self):
        annotee = getattr(self, "_quantite_vendue", None)
        if annotee is not None:
            return int(annotee or 0)
        return int(self.ventes.aggregate(total=Sum("quantite"))["total"] or 0)

    @property
    def quantite_restante(self):
        return max(0, int(self.quantite_stock or 0) - self.quantite_vendue)

    @property
    def chiffre_affaires(self):
        annote = getattr(self, "_chiffre_affaires", None)
        if annote is not None:
            return annote or Decimal("0")
        expression = ExpressionWrapper(
            F("quantite") * F("prix_vente_unitaire"),
            output_field=MONEY_FIELD,
        )
        return self.ventes.aggregate(total=Sum(expression))["total"] or Decimal("0")

    @property
    def solde(self):
        """Marge réalisée : chiffre d'affaires moins coût des unités vendues."""
        annote = getattr(self, "_solde", None)
        if annote is not None:
            return annote or Decimal("0")
        expression = ExpressionWrapper(
            F("quantite")
            * (F("prix_vente_unitaire") - F("prix_achat_unitaire")),
            output_field=MONEY_FIELD,
        )
        return self.ventes.aggregate(total=Sum(expression))["total"] or Decimal("0")

    @property
    def valeur_stock_restant(self):
        return self.quantite_restante * (self.prix_achat_unitaire or Decimal("0"))

    @property
    def stock_en_alerte(self):
        return self.quantite_restante <= int(self.seuil_alerte or 0)


class VenteFourniture(SyncTrackedModel):
    """Vente d'un produit avec conservation des prix historiques."""

    reference = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        verbose_name="Référence",
    )
    produit = models.ForeignKey(
        ProduitFourniture,
        on_delete=models.PROTECT,
        related_name="ventes",
        verbose_name="Produit",
    )
    quantite = models.PositiveIntegerField(verbose_name="Quantité vendue")
    prix_achat_unitaire = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=Decimal("0"),
        verbose_name="Prix d'achat unitaire (GNF)",
    )
    prix_vente_unitaire = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        verbose_name="Prix de vente unitaire (GNF)",
    )
    date_vente = models.DateField(default=timezone.localdate, verbose_name="Date de vente")
    acheteur = models.CharField(max_length=200, blank=True, verbose_name="Acheteur")
    observations = models.TextField(blank=True, verbose_name="Observations")
    cree_par = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes_fournitures_creees",
        verbose_name="Créée par",
    )
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vente de fourniture scolaire"
        verbose_name_plural = "Ventes de fournitures scolaires"
        ordering = ["-date_vente", "-date_creation"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantite__gte=1),
                name="vente_fourniture_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_achat_unitaire__gte=0),
                name="vente_fourniture_prix_achat_positif",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_vente_unitaire__gt=0),
                name="vente_fourniture_prix_vente_positif",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.produit.nom} x {self.quantite}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"VTE-{timezone.localdate():%Y%m%d}-{uuid4().hex[:6].upper()}"
        if self.produit_id:
            if self._state.adding:
                self.prix_achat_unitaire = self.produit.prix_achat_unitaire
            if self.prix_vente_unitaire is None:
                self.prix_vente_unitaire = self.produit.prix_vente_unitaire
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if not self.produit_id or not self.quantite:
            return
        if not self.produit.actif:
            raise ValidationError({"produit": "Ce produit est inactif."})
        deja_vendu = self.produit.ventes.exclude(pk=self.pk).aggregate(
            total=Sum("quantite")
        )["total"] or 0
        disponible = max(0, self.produit.quantite_stock - deja_vendu)
        if self.quantite > disponible:
            raise ValidationError(
                {
                    "quantite": (
                        f"Stock insuffisant : {disponible} unité(s) disponible(s)."
                    )
                }
            )

    @property
    def montant_total(self):
        return self.quantite * (self.prix_vente_unitaire or Decimal("0"))

    @property
    def cout_total(self):
        return self.quantite * (self.prix_achat_unitaire or Decimal("0"))

    @property
    def solde(self):
        return self.montant_total - self.cout_total
