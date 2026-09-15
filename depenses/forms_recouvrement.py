"""Formulaires des modules de recouvrement.

La date, l'école et l'auteur sont posés par les vues : ils n'apparaissent
jamais dans les formulaires, la date étant automatique par conception.
"""
from django import forms
from django.utils import timezone

from eleves.models import Eleve
from utilisateurs.utils import filter_by_user_school

from .models_recouvrement import (
    AbonnementInformatique, DepenseCuisine, DepenseDocument, Entree, MembrePersonnel,
    Versement,
)


class _BaseOperationForm(forms.ModelForm):
    """Applique les classes Bootstrap et normalise le montant."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nom, champ in self.fields.items():
            classe = 'form-select' if isinstance(champ.widget, forms.Select) else 'form-control'
            champ.widget.attrs.setdefault('class', classe)

    def clean_montant(self):
        montant = self.cleaned_data.get('montant')
        if montant is not None and montant <= 0:
            raise forms.ValidationError("Le montant doit être supérieur à zéro.")
        return montant


class EntreeForm(_BaseOperationForm):
    """Saisie d'une entrée d'argent : provenance, nature et mode d'encaissement."""

    class Meta:
        model = Entree
        fields = ['source', 'type_entree', 'mode_paiement', 'reference', 'montant', 'observation']
        widgets = {
            'source': forms.TextInput(attrs={'placeholder': "Ex. : don d'un parent, location de la salle"}),
            'reference': forms.TextInput(attrs={'placeholder': "Ex. : reçu n° 042 (facultatif)"}),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }


class DepenseCuisineForm(_BaseOperationForm):
    class Meta:
        model = DepenseCuisine
        fields = ['designation', 'montant', 'observation']
        widgets = {
            'designation': forms.TextInput(attrs={'placeholder': 'Ex. : riz, huile, condiments'}),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }


class DepenseDocumentForm(_BaseOperationForm):
    class Meta:
        model = DepenseDocument
        fields = ['designation', 'montant', 'observation']
        widgets = {
            'designation': forms.TextInput(attrs={'placeholder': 'Ex. : bulletins, attestations, registres'}),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }


class VersementForm(_BaseOperationForm):
    class Meta:
        model = Versement
        fields = ['lieu_versement', 'montant', 'observation']
        widgets = {
            'lieu_versement': forms.TextInput(attrs={'placeholder': "Ex. : Orabank, agence de Kipé"}),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }


class AbonnementInformatiqueForm(_BaseOperationForm):
    """Abonnement d'un élève : la liste est restreinte à son établissement."""

    class Meta:
        model = AbonnementInformatique
        fields = ['eleve', 'montant', 'date_debut', 'date_fin', 'observation']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'date_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'observation': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        eleves = Eleve.objects.filter(statut='ACTIF').select_related('classe')
        if user is not None:
            eleves = filter_by_user_school(eleves, user, 'classe__ecole')
        self.fields['eleve'].queryset = eleves.order_by('nom', 'prenom')
        self.fields['date_debut'].initial = timezone.localdate()

    def clean(self):
        donnees = super().clean()
        debut, fin = donnees.get('date_debut'), donnees.get('date_fin')
        if debut and fin and fin < debut:
            self.add_error('date_fin', "La fin de l'abonnement précède son début.")
        return donnees


class MembrePersonnelForm(forms.ModelForm):
    """Saisie d'un membre du personnel : identité, fonction et groupe.

    Les montants mensuels ne figurent pas ici : ils se saisissent directement
    dans le tableau du module, mois par mois.
    """

    class Meta:
        model = MembrePersonnel
        fields = ['prenom', 'nom', 'fonction', 'groupe', 'actif', 'observation']
        widgets = {
            'prenom': forms.TextInput(attrs={'placeholder': 'Ex. : Mariama'}),
            'nom': forms.TextInput(attrs={'placeholder': 'Ex. : Camara'}),
            'fonction': forms.TextInput(attrs={'placeholder': 'Ex. : Enseignante CP1, Surveillant, Directeur'}),
            'observation': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Facultatif'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nom, champ in self.fields.items():
            if isinstance(champ.widget, forms.CheckboxInput):
                champ.widget.attrs.setdefault('class', 'form-check-input')
            elif isinstance(champ.widget, forms.Select):
                champ.widget.attrs.setdefault('class', 'form-select')
            else:
                champ.widget.attrs.setdefault('class', 'form-control')

    def clean_prenom(self):
        return (self.cleaned_data.get('prenom') or '').strip()

    def clean_nom(self):
        return (self.cleaned_data.get('nom') or '').strip()

    def clean_fonction(self):
        return (self.cleaned_data.get('fonction') or '').strip()
