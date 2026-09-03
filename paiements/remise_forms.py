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

    # Motif obligatoire: toute remise accordée doit être justifiée.
    motif = forms.ChoiceField(
        choices=[("", "— Choisir un motif —")] + list(PaiementRemise.MOTIF_CHOICES),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select', 'required': 'required'}),
        label="Motif de la remise",
        error_messages={'required': "Le motif de la remise est obligatoire."}
    )

    # Tranches de scolarité concernées par la remise. Jamais l'inscription/réinscription.
    TRANCHE_CHOICES = [('1', '1ère tranche'), ('2', '2ème tranche'), ('3', '3ème tranche')]
    tranches = forms.MultipleChoiceField(
        choices=TRANCHE_CHOICES,
        required=False,
        initial=[],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label="Tranches concernées",
    )

    # Une remise décidée après la saisie du montant brut doit pouvoir ramener
    # le reçu au net : sinon l'encaissement et la remise couvrent deux fois la
    # même dette et le contrôle anti trop-perçu refuse l'opération.
    reduire_paiement = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Déduire la remise du montant du reçu",
    )

    # Base sur laquelle la remise est calculée pour les tranches cochées.
    base_calcul = forms.ChoiceField(
        choices=PaiementRemise.BASE_CALCUL_CHOICES,
        required=False,
        initial='TRANCHES_DUES',
        widget=forms.RadioSelect(attrs={'class': 'form-check-input base-calcul-radio'}),
        label="Base de calcul",
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
            # Repartir des choix déjà retenus quand on revient modifier les remises
            deja_applique = PaiementRemise.objects.filter(
                paiement=paiement
            ).exclude(motif='').first()
            if deja_applique:
                self.fields['motif'].initial = deja_applique.motif
            # Rouvrir l'écran doit repartir de la décision précédente, sinon
            # décocher par inadvertance restaurerait le montant brut du reçu.
            self.fields['reduire_paiement'].initial = PaiementRemise.objects.filter(
                paiement=paiement, deduite_du_paiement=True
            ).exists()
            deja_avec_tranches = PaiementRemise.objects.filter(
                paiement=paiement
            ).exclude(tranches_concernees='').first()
            if deja_avec_tranches:
                self.fields['tranches'].initial = deja_avec_tranches.tranches_concernees_liste
                if deja_avec_tranches.base_calcul:
                    self.fields['base_calcul'].initial = deja_avec_tranches.base_calcul

    def clean(self):
        cleaned_data = super().clean()
        remises = cleaned_data.get('remises') or []
        pct = cleaned_data.get('pourcentage_scolarite') or ''
        tranches = cleaned_data.get('tranches') or []
        if (remises or pct) and not tranches:
            raise forms.ValidationError(
                "Sélectionnez au moins une tranche concernée par la remise."
            )
        if not cleaned_data.get('base_calcul'):
            cleaned_data['base_calcul'] = 'TRANCHES_DUES'
        return cleaned_data

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
