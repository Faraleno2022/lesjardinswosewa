from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from decimal import Decimal
from eleves.models import Eleve, Ecole
from .models import (
    Depense, CategorieDepense, Fournisseur, 
    PieceJustificative, BudgetAnnuel
)
from .models_logistique import (
    CategorieArticle, Article, BienEtablissement, MouvementStock,
    Inventaire, LigneInventaire, ContributionPapierRam
)
from .models_bibliotheque import Livre, Emprunt, Reservation

class DepenseForm(forms.ModelForm):
    """Formulaire simplifié pour les dépenses"""
    
    class Meta:
        model = Depense
        fields = ['date_facture', 'description', 'montant_ht']
        widgets = {
            'date_facture': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'placeholder': 'Date de la dépense'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la dépense'
            }),
            'montant_ht': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'Montant en GNF'
            }),
        }
        labels = {
            'date_facture': 'Date',
            'description': 'Description',
            'montant_ht': 'Montant (GNF)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre tous les champs obligatoires
        self.fields['date_facture'].required = True
        self.fields['description'].required = True
        self.fields['montant_ht'].required = True

    def clean_montant_ht(self):
        montant_ht = self.cleaned_data.get('montant_ht')
        if montant_ht and montant_ht <= 0:
            raise ValidationError("Le montant doit être supérieur à 0.")
        return montant_ht

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Définir des valeurs par défaut pour les champs non inclus dans le formulaire
        if not instance.numero_facture:
            # Générer un numéro de facture automatique
            from datetime import datetime
            now = datetime.now()
            instance.numero_facture = f"DEP-{now.strftime('%Y%m%d-%H%M%S')}"
        
        if not instance.libelle:
            # Utiliser les 50 premiers caractères de la description comme libellé
            instance.libelle = instance.description[:50] if instance.description else "Dépense"
        
        # Créer ou récupérer une catégorie par défaut
        if not hasattr(instance, 'categorie') or not instance.categorie_id:
            categorie_defaut, created = CategorieDepense.objects.get_or_create(
                code='GENERAL',
                defaults={
                    'nom': 'Dépenses générales',
                    'description': 'Catégorie par défaut pour les dépenses',
                    'actif': True
                }
            )
            instance.categorie = categorie_defaut
        
        # Créer ou récupérer un fournisseur par défaut
        if not hasattr(instance, 'fournisseur') or not instance.fournisseur_id:
            fournisseur_defaut, created = Fournisseur.objects.get_or_create(
                nom='Fournisseur général',
                defaults={
                    'type_fournisseur': 'ENTREPRISE',
                    'adresse': 'Adresse non spécifiée',
                    'telephone': '000000000',
                    'actif': True
                }
            )
            instance.fournisseur = fournisseur_defaut
        
        # Valeurs par défaut
        instance.statut = 'VALIDEE'  # Statut par défaut
        instance.taux_tva = Decimal('0')  # Pas de TVA par défaut
        instance.date_echeance = instance.date_facture  # Même date que la facture
        instance.type_depense = 'FONCTIONNEMENT'  # Type par défaut
        
        if commit:
            instance.save()
        return instance

class CategorieDepenseForm(forms.ModelForm):
    """Formulaire pour les catégories de dépenses"""
    
    class Meta:
        model = CategorieDepense
        fields = ['nom', 'description', 'code', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la catégorie'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description de la catégorie'
            }),
            'code': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Code (ex: FONC, INV, PERS)'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()
            # Vérifier l'unicité du code
            if self.instance.pk:
                if CategorieDepense.objects.exclude(pk=self.instance.pk).filter(code=code).exists():
                    raise ValidationError("Ce code existe déjà.")
            else:
                if CategorieDepense.objects.filter(code=code).exists():
                    raise ValidationError("Ce code existe déjà.")
        return code

class FournisseurForm(forms.ModelForm):
    """Formulaire pour les fournisseurs"""
    
    class Meta:
        model = Fournisseur
        fields = [
            'nom', 'type_fournisseur', 'adresse', 'telephone', 'email',
            'numero_compte', 'banque', 'numero_nif', 'numero_rccm', 'actif'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du fournisseur'
            }),
            'type_fournisseur': forms.Select(attrs={'class': 'form-control'}),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de téléphone'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'Adresse email'
            }),
            'numero_compte': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de compte bancaire'
            }),
            'banque': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de la banque'
            }),
            'numero_nif': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro NIF'
            }),
            'numero_rccm': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro RCCM'
            }),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            # Supprimer les espaces et caractères spéciaux
            telephone = ''.join(filter(str.isdigit, telephone))
            if len(telephone) < 8:
                raise ValidationError("Le numéro de téléphone doit contenir au moins 8 chiffres.")
        return telephone

class PieceJustificativeForm(forms.ModelForm):
    """Formulaire pour les pièces justificatives"""
    
    class Meta:
        model = PieceJustificative
        fields = ['type_piece', 'nom_fichier', 'fichier', 'description']
        widgets = {
            'type_piece': forms.Select(attrs={'class': 'form-control'}),
            'nom_fichier': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom du fichier'
            }),
            'fichier': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Description du document'
            }),
        }

    def clean_fichier(self):
        fichier = self.cleaned_data.get('fichier')
        if fichier:
            # Vérifier la taille du fichier (max 10MB)
            if fichier.size > 10 * 1024 * 1024:
                raise ValidationError("La taille du fichier ne doit pas dépasser 10 MB.")
            
            # Vérifier l'extension
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.doc', '.docx']
            file_extension = fichier.name.lower().split('.')[-1]
            if f'.{file_extension}' not in allowed_extensions:
                raise ValidationError("Format de fichier non autorisé. Formats acceptés: PDF, JPG, PNG, DOC, DOCX.")
        
        return fichier

class BudgetAnnuelForm(forms.ModelForm):
    """Formulaire pour le budget annuel"""
    
    class Meta:
        model = BudgetAnnuel
        fields = ['annee', 'categorie', 'budget_prevu']
        widgets = {
            'annee': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '2020',
                'max': '2030',
                'placeholder': 'Année'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'budget_prevu': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1',
                'min': '0',
                'placeholder': 'Budget prévu en GNF'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categorie'].queryset = CategorieDepense.objects.filter(actif=True)

    def clean_budget_prevu(self):
        budget_prevu = self.cleaned_data.get('budget_prevu')
        if budget_prevu and budget_prevu <= 0:
            raise ValidationError("Le budget prévu doit être supérieur à 0.")
        return budget_prevu

    def clean(self):
        cleaned_data = super().clean()
        annee = cleaned_data.get('annee')
        categorie = cleaned_data.get('categorie')
        
        if annee and categorie:
            # Vérifier qu'il n'existe pas déjà un budget pour cette année et catégorie
            if self.instance.pk:
                existing = BudgetAnnuel.objects.exclude(pk=self.instance.pk).filter(
                    annee=annee, categorie=categorie
                )
            else:
                existing = BudgetAnnuel.objects.filter(annee=annee, categorie=categorie)
            
            if existing.exists():
                raise ValidationError("Un budget existe déjà pour cette catégorie et cette année.")
        
        return cleaned_data

class RechercheDepenseForm(forms.Form):
    """Formulaire de recherche pour les dépenses"""
    
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher par libellé, numéro de facture...'
        })
    )
    
    statut = forms.ChoiceField(
        required=False,
        choices=[('', 'Tous les statuts')] + Depense.STATUT_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    categorie = forms.ModelChoiceField(
        required=False,
        queryset=CategorieDepense.objects.filter(actif=True),
        empty_label="Toutes les catégories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    fournisseur = forms.ModelChoiceField(
        required=False,
        queryset=Fournisseur.objects.filter(actif=True),
        empty_label="Tous les fournisseurs",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        
        if date_debut and date_fin:
            if date_fin < date_debut:
                raise ValidationError("La date de fin ne peut pas être antérieure à la date de début.")
        
        return cleaned_data


# ===== FORMULAIRES LOGISTIQUE =====

class CategorieArticleForm(forms.ModelForm):
    """Formulaire pour les catégories d'articles (stock)"""

    class Meta:
        model = CategorieArticle
        fields = ['nom', 'code', 'type_categorie', 'description', 'actif']
        widgets = {
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nom de la catégorie'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Code (ex: FOURN, MOBIL)'}),
            'type_categorie': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            qs = CategorieArticle.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ce code existe déjà.")
        return code


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = [
            'code_article', 'nom', 'categorie', 'description', 'marque', 'reference',
            'unite_mesure', 'stock_minimum', 'stock_maximum', 'prix_unitaire',
            'etat', 'emplacement', 'photo'
        ]
        widgets = {
            'code_article': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'marque': forms.TextInput(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'unite_mesure': forms.Select(attrs={'class': 'form-control'}),
            'stock_minimum': forms.NumberInput(attrs={'class': 'form-control'}),
            'stock_maximum': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control'}),
            'etat': forms.Select(attrs={'class': 'form-control'}),
            'emplacement': forms.TextInput(attrs={'class': 'form-control'}),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le code est généré automatiquement si laissé vide
        self.fields['code_article'].required = False
        self.fields['code_article'].widget.attrs['placeholder'] = 'Laissez vide pour génération automatique'
        # Limiter aux catégories actives
        self.fields['categorie'].queryset = CategorieArticle.objects.filter(actif=True)

    def clean_code_article(self):
        code = self.cleaned_data.get('code_article')
        if code:
            code = code.strip().upper()
            qs = Article.objects.filter(code_article=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Ce code article existe déjà.")
        return code


class BienEtablissementForm(forms.ModelForm):
    class Meta:
        model = BienEtablissement
        fields = [
            'ecole', 'code_bien', 'nom', 'type_bien', 'marque',
            'quantite_achetee', 'prix_achat_unitaire', 'quantite_utilisee',
            'quantite_gatee', 'localisation', 'date_acquisition',
            'description', 'observations'
        ]
        widgets = {
            'ecole': forms.Select(attrs={'class': 'form-select'}),
            'code_bien': forms.TextInput(attrs={'class': 'form-control'}),
            'nom': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex. Tables, marqueurs, ordinateurs'}),
            'type_bien': forms.Select(attrs={'class': 'form-select'}),
            'marque': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Marque (facultatif)'}),
            'quantite_achetee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'prix_achat_unitaire': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1}),
            'quantite_utilisee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'quantite_gatee': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'localisation': forms.TextInput(attrs={'class': 'form-control'}),
            'date_acquisition': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, ecole=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.ecole_utilisateur = ecole
        self.fields['code_bien'].required = False
        self.fields['code_bien'].widget.attrs['placeholder'] = 'Généré automatiquement si vide'
        self.fields['ecole'].queryset = Ecole.objects.order_by('nom')
        if ecole:
            self.fields['ecole'].queryset = Ecole.objects.filter(pk=ecole.pk)
            self.fields['ecole'].initial = ecole
            self.fields['ecole'].widget = forms.HiddenInput()

    def clean_ecole(self):
        if self.ecole_utilisateur:
            return self.ecole_utilisateur
        return self.cleaned_data.get('ecole')

    def clean(self):
        cleaned = super().clean()
        achetee = cleaned.get('quantite_achetee') or 0
        utilisee = cleaned.get('quantite_utilisee') or 0
        gatee = cleaned.get('quantite_gatee') or 0
        if utilisee + gatee > achetee:
            raise ValidationError(
                "La quantité utilisée et la quantité gâtée ne peuvent pas dépasser la quantité achetée."
            )
        return cleaned


class ContributionPapierRamForm(forms.ModelForm):
    class Meta:
        model = ContributionPapierRam
        fields = [
            'eleve', 'annee_scolaire', 'mode_contribution', 'nombre_paquets',
            'montant_paye', 'date_contribution', 'observations'
        ]
        widgets = {
            'eleve': forms.Select(attrs={'class': 'form-select', 'id': 'id_eleve'}),
            'annee_scolaire': forms.TextInput(attrs={'class': 'form-control', 'readonly': True}),
            'mode_contribution': forms.Select(attrs={'class': 'form-select', 'id': 'id_mode_contribution'}),
            'nombre_paquets': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'id': 'id_nombre_paquets'}),
            'montant_paye': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 1, 'id': 'id_montant_paye'}),
            'date_contribution': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, ecole=None, annee_scolaire=None, **kwargs):
        super().__init__(*args, **kwargs)
        eleves = Eleve.objects.select_related('classe', 'classe__ecole').filter(statut='ACTIF')
        if ecole:
            eleves = eleves.filter(classe__ecole=ecole)
        if annee_scolaire:
            eleves = eleves.filter(classe__annee_scolaire=annee_scolaire)
            self.fields['annee_scolaire'].initial = annee_scolaire
        if self.instance.pk:
            eleves = Eleve.objects.filter(Q(pk=self.instance.eleve_id) | Q(pk__in=eleves.values('pk')))
        self.fields['eleve'].queryset = eleves.order_by('classe__nom', 'nom', 'prenom')
        self.fields['eleve'].label_from_instance = (
            lambda eleve: f"{eleve.matricule} — {eleve.prenom} {eleve.nom} ({eleve.classe.nom})"
        )

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('mode_contribution')
        if mode == 'PAPIER':
            if (cleaned.get('nombre_paquets') or 0) < 1:
                self.add_error('nombre_paquets', "Indiquez au moins un paquet remis.")
            cleaned['montant_paye'] = Decimal('0')
        elif mode == 'ARGENT':
            if (cleaned.get('montant_paye') or Decimal('0')) <= 0:
                self.add_error('montant_paye', "Indiquez le montant payé.")
            cleaned['nombre_paquets'] = 0
        return cleaned


class MouvementStockForm(forms.ModelForm):
    class Meta:
        model = MouvementStock
        fields = [
            'article', 'type_mouvement', 'motif', 'quantite',
            'prix_unitaire', 'date_mouvement', 'destinataire',
            'document_reference', 'observations'
        ]
        widgets = {
            'article': forms.Select(attrs={'class': 'form-control'}),
            'type_mouvement': forms.Select(attrs={'class': 'form-control'}),
            'motif': forms.Select(attrs={'class': 'form-control'}),
            'quantite': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_unitaire': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_mouvement': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'destinataire': forms.TextInput(attrs={'class': 'form-control'}),
            'document_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class InventaireForm(forms.ModelForm):
    class Meta:
        model = Inventaire
        fields = ['date_inventaire', 'description', 'observations']
        widgets = {
            'date_inventaire': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LigneInventaireForm(forms.ModelForm):
    class Meta:
        model = LigneInventaire
        fields = ['article', 'stock_physique', 'observations']
        widgets = {
            'article': forms.Select(attrs={'class': 'form-control'}),
            'stock_physique': forms.NumberInput(attrs={'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


# ===== FORMULAIRES BIBLIOTHÈQUE =====

class LivreForm(forms.ModelForm):
    class Meta:
        model = Livre
        fields = [
            'code_livre', 'isbn', 'titre', 'auteur', 'categorie', 'editeur',
            'annee_publication', 'edition', 'langue', 'nombre_pages', 'resume',
            'mots_cles', 'emplacement', 'etat', 'nombre_exemplaires',
            'prix_acquisition', 'date_acquisition', 'couverture'
        ]
        widgets = {
            'code_livre': forms.TextInput(attrs={'class': 'form-control'}),
            'isbn': forms.TextInput(attrs={'class': 'form-control'}),
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'auteur': forms.TextInput(attrs={'class': 'form-control'}),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'editeur': forms.TextInput(attrs={'class': 'form-control'}),
            'annee_publication': forms.NumberInput(attrs={'class': 'form-control'}),
            'edition': forms.TextInput(attrs={'class': 'form-control'}),
            'langue': forms.TextInput(attrs={'class': 'form-control'}),
            'nombre_pages': forms.NumberInput(attrs={'class': 'form-control'}),
            'resume': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'mots_cles': forms.TextInput(attrs={'class': 'form-control'}),
            'emplacement': forms.TextInput(attrs={'class': 'form-control'}),
            'etat': forms.Select(attrs={'class': 'form-control'}),
            'nombre_exemplaires': forms.NumberInput(attrs={'class': 'form-control'}),
            'prix_acquisition': forms.NumberInput(attrs={'class': 'form-control'}),
            'date_acquisition': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'couverture': forms.FileInput(attrs={'class': 'form-control'}),
        }


class EmpruntForm(forms.ModelForm):
    class Meta:
        model = Emprunt
        fields = ['livre', 'eleve', 'date_retour_prevue', 'observations_emprunt']
        widgets = {
            'livre': forms.Select(attrs={'class': 'form-control'}),
            'eleve': forms.Select(attrs={'class': 'form-control'}),
            'date_retour_prevue': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observations_emprunt': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ReservationForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        livres = Livre.objects.filter(actif=True).order_by('titre')
        eleves = Eleve.objects.filter(statut='ACTIF').select_related(
            'classe', 'classe__ecole'
        ).order_by('nom', 'prenom')

        if user is not None:
            from utilisateurs.utils import user_is_superadmin, user_school

            if not user_is_superadmin(user):
                ecole = user_school(user)
                if ecole is None:
                    livres = livres.none()
                    eleves = eleves.none()
                else:
                    livres = livres.filter(cree_par__profil__ecole=ecole)
                    eleves = eleves.filter(classe__ecole=ecole)

        self.fields['livre'].queryset = livres
        self.fields['eleve'].queryset = eleves

    class Meta:
        model = Reservation
        fields = ['livre', 'eleve', 'observations']
        widgets = {
            'livre': forms.Select(attrs={'class': 'form-select'}),
            'eleve': forms.Select(attrs={'class': 'form-select'}),
            'observations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Précisions éventuelles sur la réservation',
            }),
        }
