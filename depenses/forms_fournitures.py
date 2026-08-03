"""Formulaires du module de vente de fournitures scolaires."""

from decimal import Decimal
from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from eleves.models import Ecole

from .models_fournitures import ProduitFourniture, VenteFourniture


class ProduitFournitureForm(forms.ModelForm):
    class Meta:
        model = ProduitFourniture
        fields = [
            "ecole",
            "code_produit",
            "nom",
            "description",
            "quantite_stock",
            "prix_achat_unitaire",
            "prix_vente_unitaire",
            "seuil_alerte",
            "actif",
        ]
        widgets = {
            "ecole": forms.Select(attrs={"class": "form-select"}),
            "code_produit": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Généré automatiquement si vide"}
            ),
            "nom": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Ex. Cahier 100 pages"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "quantite_stock": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "prix_achat_unitaire": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "step": 1}
            ),
            "prix_vente_unitaire": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "step": 1}
            ),
            "seuil_alerte": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "actif": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, ecole=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ecole_utilisateur = ecole
        self.fields["code_produit"].required = False
        self.fields["ecole"].queryset = Ecole.objects.order_by("nom")
        if ecole:
            self.fields["ecole"].queryset = Ecole.objects.filter(pk=ecole.pk)
            self.fields["ecole"].initial = ecole
            self.fields["ecole"].disabled = True
            self.fields["ecole"].widget = forms.HiddenInput()

    def clean_ecole(self):
        return self.ecole_utilisateur or self.cleaned_data.get("ecole")

    def clean_code_produit(self):
        code = (self.cleaned_data.get("code_produit") or "").strip().upper()
        if not code:
            code = f"FOUR-{uuid4().hex[:8].upper()}"
        ecole = self.ecole_utilisateur or self.cleaned_data.get("ecole")
        if code and ecole:
            qs = ProduitFourniture.objects.filter(ecole=ecole, code_produit=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ce code produit existe déjà dans cette école.")
        return code

    def clean_quantite_stock(self):
        quantite = self.cleaned_data.get("quantite_stock") or 0
        if self.instance.pk and quantite < self.instance.quantite_vendue:
            raise ValidationError(
                f"{self.instance.quantite_vendue} unité(s) sont déjà vendues. "
                "Le stock total ne peut pas être inférieur."
            )
        return quantite

    def clean_prix_vente_unitaire(self):
        prix = self.cleaned_data.get("prix_vente_unitaire") or Decimal("0")
        if prix <= 0:
            raise ValidationError("Le prix de vente doit être supérieur à zéro.")
        return prix


class VenteFournitureForm(forms.ModelForm):
    class Meta:
        model = VenteFourniture
        fields = [
            "quantite",
            "prix_vente_unitaire",
            "date_vente",
            "acheteur",
            "observations",
        ]
        widgets = {
            "quantite": forms.NumberInput(attrs={"class": "form-control", "min": 1}),
            "prix_vente_unitaire": forms.NumberInput(
                attrs={"class": "form-control", "min": 1, "step": 1}
            ),
            "date_vente": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
            "acheteur": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Nom de l'élève ou du client (facultatif)"}
            ),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, produit=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.produit = produit
        if not self.is_bound:
            self.fields["date_vente"].initial = timezone.localdate()
            if produit:
                self.fields["prix_vente_unitaire"].initial = produit.prix_vente_unitaire

    def clean_quantite(self):
        quantite = self.cleaned_data.get("quantite") or 0
        if quantite < 1:
            raise ValidationError("La quantité vendue doit être supérieure à zéro.")
        if self.produit and quantite > self.produit.quantite_restante:
            raise ValidationError(
                f"Stock insuffisant : {self.produit.quantite_restante} unité(s) disponible(s)."
            )
        return quantite

    def clean_prix_vente_unitaire(self):
        prix = self.cleaned_data.get("prix_vente_unitaire") or Decimal("0")
        if prix <= 0:
            raise ValidationError("Le prix de vente doit être supérieur à zéro.")
        return prix
