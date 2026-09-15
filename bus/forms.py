from django import forms

from eleves.models import Classe, Eleve
from utilisateurs.utils import filter_by_user_school, user_is_superadmin

from .models import AbonnementBus, AbonnementCantine


class EleveParClasseSelect(forms.Select):
    """Ajoute la classe de l'élève à chaque option du menu déroulant."""

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name, value, label, selected, index, subindex=subindex, attrs=attrs
        )
        instance = getattr(value, "instance", None)
        if instance is not None:
            option["attrs"]["data-classe-id"] = str(instance.classe_id)
        return option


class EleveChoiceField(forms.ModelChoiceField):
    widget = EleveParClasseSelect

    def label_from_instance(self, eleve):
        return f"{eleve.matricule} — {eleve.prenom} {eleve.nom}"


class ClasseChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, afficher_ecole=False, **kwargs):
        self.afficher_ecole = afficher_ecole
        super().__init__(*args, **kwargs)

    def label_from_instance(self, classe):
        libelle = f"{classe.nom} — {classe.annee_scolaire}"
        if self.afficher_ecole:
            return f"{classe.ecole.nom} / {libelle}"
        return libelle


class EleveParClasseFormMixin:
    """Sécurise et prépare la sélection classe → élève pour une école."""

    def _configure_eleve_selection(self, user):
        classes = Classe.objects.select_related("ecole")
        eleves = Eleve.objects.filter(est_dans_corbeille=False).select_related(
            "classe", "classe__ecole", "responsable_principal"
        )

        if user is None:
            # Les vues doivent toujours transmettre l'utilisateur. En cas d'oubli,
            # ne jamais exposer les élèves de toutes les écoles.
            classes = classes.none()
            eleves = eleves.none()
        else:
            classes = filter_by_user_school(classes, user, "ecole")
            eleves = filter_by_user_school(eleves, user, "classe__ecole")

        self.fields["classe"].queryset = classes.order_by(
            "ecole__nom", "annee_scolaire", "nom"
        )
        self.fields["eleve"].queryset = eleves.order_by(
            "classe__nom", "prenom", "nom", "matricule"
        )
        self.fields["classe"].afficher_ecole = bool(
            user and user_is_superadmin(user)
        )

        classe_initiale = None
        if self.is_bound:
            classe_initiale = self.data.get(self.add_prefix("classe"))
        if not classe_initiale:
            classe_initiale = self.initial.get("classe")
        if not classe_initiale and getattr(self.instance, "eleve_id", None):
            classe_initiale = self.instance.eleve.classe_id
        if classe_initiale:
            self.initial["classe"] = classe_initiale

    def clean(self):
        cleaned_data = super().clean()
        classe = cleaned_data.get("classe")
        eleve = cleaned_data.get("eleve")
        if classe and eleve and eleve.classe_id != classe.pk:
            self.add_error(
                "eleve",
                "L'élève sélectionné n'appartient pas à la classe choisie.",
            )
        return cleaned_data


class AbonnementBusForm(EleveParClasseFormMixin, forms.ModelForm):
    classe = ClasseChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        empty_label="Toutes les classes",
        label="Filtrer par classe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    eleve = EleveChoiceField(
        queryset=Eleve.objects.none(),
        empty_label="Sélectionnez un élève",
        label="Élève",
        widget=EleveParClasseSelect(attrs={"class": "form-select"}),
    )

    class Meta:
        model = AbonnementBus
        fields = [
            "classe", "eleve", "montant", "reference_externe", "periodicite",
            "date_debut", "date_expiration", "statut", "alerte_avant_jours",
            "zone", "itineraire", "point_arret", "contact_parent", "observations",
        ]
        widgets = {
            "montant": forms.NumberInput(attrs={"class": "form-control"}),
            "periodicite": forms.Select(attrs={"class": "form-select"}),
            "date_debut": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "date_expiration": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "statut": forms.Select(attrs={"class": "form-select"}),
            "alerte_avant_jours": forms.NumberInput(attrs={"class": "form-control"}),
            "zone": forms.TextInput(attrs={"class": "form-control"}),
            "itineraire": forms.TextInput(attrs={"class": "form-control"}),
            "point_arret": forms.TextInput(attrs={"class": "form-control"}),
            "contact_parent": forms.TextInput(attrs={"class": "form-control"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "reference_externe": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "N° reçu, Mobile Money, chèque…",
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_eleve_selection(user)


class AbonnementCantineForm(EleveParClasseFormMixin, forms.ModelForm):
    classe = ClasseChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        empty_label="Toutes les classes",
        label="Filtrer par classe",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    eleve = EleveChoiceField(
        queryset=Eleve.objects.none(),
        empty_label="Sélectionnez un élève",
        label="Élève",
        widget=EleveParClasseSelect(attrs={"class": "form-select"}),
    )

    class Meta:
        model = AbonnementCantine
        fields = [
            "classe", "eleve", "montant", "reference_externe", "periodicite",
            "type_repas", "date_debut", "date_expiration", "statut",
            "alerte_avant_jours", "regime_alimentaire", "allergies",
            "contact_parent", "observations",
        ]
        widgets = {
            "date_debut": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "date_expiration": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "montant": forms.NumberInput(attrs={"class": "form-control", "placeholder": "Montant en GNF"}),
            "reference_externe": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "N° reçu, Mobile Money, chèque…",
            }),
            "periodicite": forms.Select(attrs={"class": "form-select"}),
            "type_repas": forms.Select(attrs={"class": "form-select"}),
            "statut": forms.Select(attrs={"class": "form-select"}),
            "alerte_avant_jours": forms.NumberInput(attrs={"class": "form-control"}),
            "regime_alimentaire": forms.TextInput(attrs={"class": "form-control", "placeholder": "Ex: Végétarien, Halal, etc."}),
            "allergies": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Indiquez les allergies alimentaires"}),
            "contact_parent": forms.TextInput(attrs={"class": "form-control", "placeholder": "+224XXXXXXXXX"}),
            "observations": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._configure_eleve_selection(user)
