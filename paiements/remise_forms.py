from django import forms
from decimal import Decimal
from .models import RemiseReduction, PaiementRemise


class PaiementRemiseForm(forms.Form):
    """Formulaire pour appliquer des remises à un paiement"""
    
    remises = forms.ModelMultipleChoiceField(
        queryset=RemiseReduction.objects.filter(actif=True),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'form-check-input'
        }),
        required=False,
        label="Remises disponibles"
    )
    
    montant_original = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'readonly': True
        }),
        label="Montant original"
    )

    # Nouveau: pourcentage scolarité sélectionnable par l'utilisateur (1 à 10%)
    POURCENT_CHOICES = [("", "— Choisir —")] + [(str(i), f"{i}%") for i in range(1, 101)]
    pourcentage_scolarite = forms.ChoiceField(
        choices=POURCENT_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Remise scolarité (%)"
    )
    
    def __init__(self, *args, **kwargs):
        paiement = kwargs.pop('paiement', None)
        super().__init__(*args, **kwargs)
        
        if paiement:
            self.fields['montant_original'].initial = paiement.montant
            # Filtrer les remises valides à la date du paiement
            today = paiement.date_paiement
            self.fields['remises'].queryset = RemiseReduction.objects.filter(
                actif=True,
                date_debut__lte=today,
                date_fin__gte=today
            )
    
    def calculate_total_remise(self, montant_base):
        """Calcule le montant total des remises sélectionnées"""
        remises = self.cleaned_data.get('remises', [])
        total_remise = Decimal('0')
        
        for remise in remises:
            montant_remise = remise.calculer_remise(montant_base)
            total_remise += montant_remise
        
        return min(total_remise, montant_base)  # La remise ne peut pas dépasser le montant
    
    def get_remises_details(self, montant_base):
        """Retourne les détails de chaque remise appliquée"""
        remises = self.cleaned_data.get('remises', [])
        details = []
        
        for remise in remises:
            montant_remise = remise.calculer_remise(montant_base)
            details.append({
                'remise': remise,
                'montant': montant_remise,
                'description': f"{remise.nom} - {montant_remise:,.0f} GNF".replace(',', ' ')
            })
        
        return details


class CalculateurRemiseForm(forms.Form):
    """Formulaire pour calculer les remises en temps réel"""
    
    montant = forms.DecimalField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Montant en GNF',
            'min': '0',
            'step': '1000'
        }),
        label="Montant du paiement"
    )
    
    remise_id = forms.ModelChoiceField(
        queryset=RemiseReduction.objects.filter(actif=True),
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        required=False,
        empty_label="Sélectionner une remise",
        label="Remise à appliquer"
    )
    
    def calculate_remise_preview(self):
        """Calcule un aperçu de la remise"""
        if not self.is_valid():
            return None
            
        montant = self.cleaned_data.get('montant')
        remise = self.cleaned_data.get('remise_id')
        
        if not montant or not remise:
            return None
            
        montant_remise = remise.calculer_remise(montant)
        montant_final = montant - montant_remise
        
        return {
            'montant_original': montant,
            'montant_remise': montant_remise,
            'montant_final': montant_final,
            'pourcentage_remise': (montant_remise / montant * 100) if montant > 0 else 0,
            'remise_nom': remise.nom,
            'remise_type': remise.get_type_remise_display()
        }
