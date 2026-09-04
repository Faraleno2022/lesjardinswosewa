from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal
from .models import (
    AffectationClasse,
    AvanceSalaire,
    Enseignant,
    EtatSalaire,
    PeriodeSalaire,
    PresenceEnseignant,
    NIVEAUX_CLASSES_ENSEIGNANT,
    StatutAvanceSalaire,
    StatutEnseignant,
    TypeEnseignant,
)
from eleves.models import Ecole, Classe


def classes_affectables(ecole_id, type_enseignant, inclure_ids=()):
    """Classes compatibles de l'année récente, limitées à une école."""
    niveaux = NIVEAUX_CLASSES_ENSEIGNANT.get(type_enseignant, ())
    if not ecole_id or not niveaux:
        return Classe.objects.none()

    toutes = Classe.objects.filter(
        ecole_id=ecole_id,
        niveau__in=niveaux,
    )
    annee_recente = (
        toutes.order_by('-annee_scolaire')
        .values_list('annee_scolaire', flat=True)
        .first()
    )
    if not annee_recente:
        return toutes.none()

    filtre = Q(annee_scolaire=annee_recente)
    ids = tuple(inclure_ids or ())
    if ids:
        filtre |= Q(pk__in=ids)
    return toutes.filter(filtre).order_by(
        '-annee_scolaire',
        'niveau',
        'nom',
    )


class EnseignantForm(forms.ModelForm):
    """Formulaire pour créer/modifier un enseignant"""

    classe_principale = forms.ModelChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label='Classe principale',
        help_text='Pour un enseignant de maternelle ou du primaire.',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    classes_secondaire = forms.ModelMultipleChoiceField(
        queryset=Classe.objects.none(),
        required=False,
        label='Classes affectées',
        help_text=(
            'Pour le secondaire. Maintenez Ctrl (Windows) ou Commande (Mac) '
            'pour sélectionner plusieurs classes.'
        ),
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '6',
        }),
    )
    matiere_affectation = forms.CharField(
        required=False,
        max_length=100,
        label='Matière des nouvelles affectations',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex. Mathématiques',
        }),
    )
    heures_affectation = forms.DecimalField(
        required=False,
        min_value=Decimal('0.25'),
        max_value=Decimal('168'),
        max_digits=5,
        decimal_places=2,
        label='Heures par semaine',
        help_text='Obligatoire lorsqu’une nouvelle classe secondaire est sélectionnée.',
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.25',
            'min': '0.25',
            'max': '168',
        }),
    )
    
    class Meta:
        model = Enseignant
        fields = [
            'nom', 'prenoms', 'telephone', 'adresse',
            'ecole', 'type_enseignant', 'statut', 
            'taux_horaire', 'salaire_fixe', 'heures_mensuelles', 'date_embauche'
        ]
        widgets = {
            'nom': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nom de famille'
            }),
            'prenoms': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Prénoms'
            }),
            'telephone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+224 XXX XX XX XX'
            }),
            'adresse': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Adresse complète'
            }),
            'ecole': forms.Select(attrs={
                'class': 'form-select'
            }),
            'type_enseignant': forms.Select(attrs={
                'class': 'form-select'
            }),
            'statut': forms.Select(attrs={
                'class': 'form-select'
            }),
            'taux_horaire': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Taux horaire en GNF',
                'step': '0.01'
            }),
            'salaire_fixe': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Salaire fixe en GNF',
                'step': '0.01'
            }),
            'heures_mensuelles': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre d\'heures par mois',
                'step': '0.25',
                'min': '0'
            }),
            'date_embauche': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }
        labels = {
            'nom': 'Nom de famille *',
            'prenoms': 'Prénoms *',
            'telephone': 'Téléphone',
            'adresse': 'Adresse',
            'ecole': 'École *',
            'type_enseignant': 'Type d\'enseignant *',
            'statut': 'Statut',
            'taux_horaire': 'Taux horaire (GNF)',
            'salaire_fixe': 'Salaire fixe (GNF)',
            'heures_mensuelles': 'Volume mensuel indicatif',
            'date_embauche': 'Date d\'embauche *',
        }
        help_texts = {
            'taux_horaire': 'Pour le secondaire. Le salaire est calculé avec les heures réelles.',
            'salaire_fixe': 'Montant mensuel négocié pour garderie, maternelle, primaire et cadres/administrateurs',
            'heures_mensuelles': 'Optionnel et indicatif. Les heures payées viennent des pointages ou de la saisie globale du mois.',
            'date_embauche': 'Date d\'entrée en fonction',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.est_creation = not bool(self.instance.pk)
        
        # Rendre certains champs obligatoires
        self.fields['nom'].required = True
        self.fields['prenoms'].required = True
        self.fields['ecole'].required = True
        self.fields['type_enseignant'].required = True
        self.fields['date_embauche'].required = True
        
        # Restreindre les écoles visibles selon l'utilisateur
        if self.user:
            from utilisateurs.utils import user_is_admin, user_school
            if not user_is_admin(self.user):
                ecole_user = user_school(self.user)
                if ecole_user:
                    self.fields['ecole'].queryset = Ecole.objects.filter(id=ecole_user.id)
                    self.fields['ecole'].initial = ecole_user
        
        # Définir le statut par défaut
        if not self.instance.pk:
            self.fields['statut'].initial = StatutEnseignant.ACTIF

        if self.is_bound:
            ecole_id = self.data.get(self.add_prefix('ecole'))
            type_enseignant = self.data.get(self.add_prefix('type_enseignant'))
        else:
            ecole_initiale = (
                self.instance.ecole_id
                if self.instance.pk
                else self.initial.get('ecole')
            )
            if hasattr(ecole_initiale, 'pk'):
                ecole_initiale = ecole_initiale.pk
            if not ecole_initiale and self.user:
                from utilisateurs.utils import user_school
                ecole_user = user_school(self.user)
                ecole_initiale = getattr(ecole_user, 'pk', None)
            ecole_id = ecole_initiale
            type_enseignant = (
                self.instance.type_enseignant
                if self.instance.pk
                else self.initial.get('type_enseignant')
            )

        affectations_actives = AffectationClasse.objects.none()
        if self.instance.pk:
            affectations_actives = self.instance.affectations.filter(actif=True)
        ids_actifs = tuple(
            affectations_actives.values_list('classe_id', flat=True)
        )

        if type_enseignant in (
            TypeEnseignant.MATERNELLE,
            TypeEnseignant.PRIMAIRE,
        ):
            self.fields['classe_principale'].queryset = classes_affectables(
                ecole_id,
                type_enseignant,
                ids_actifs,
            )
        if type_enseignant == TypeEnseignant.SECONDAIRE:
            self.fields['classes_secondaire'].queryset = classes_affectables(
                ecole_id,
                type_enseignant,
                ids_actifs,
            )

        if not self.is_bound and self.instance.pk:
            if type_enseignant == TypeEnseignant.SECONDAIRE:
                self.initial['classes_secondaire'] = ids_actifs
            elif type_enseignant in (
                TypeEnseignant.MATERNELLE,
                TypeEnseignant.PRIMAIRE,
            ):
                classe_id = next(iter(ids_actifs), None)
                if classe_id:
                    self.initial['classe_principale'] = classe_id

    def clean(self):
        cleaned_data = super().clean()
        type_enseignant = cleaned_data.get('type_enseignant')
        taux_horaire = cleaned_data.get('taux_horaire')
        salaire_fixe = cleaned_data.get('salaire_fixe')
        heures_mensuelles = cleaned_data.get('heures_mensuelles')
        classe_principale = cleaned_data.get('classe_principale')
        classes_secondaire = cleaned_data.get('classes_secondaire')
        heures_affectation = cleaned_data.get('heures_affectation')

        # Validation selon le type d'enseignant
        if type_enseignant == TypeEnseignant.SECONDAIRE:
            if not taux_horaire:
                raise ValidationError({
                    'taux_horaire': 'Le taux horaire est obligatoire pour les enseignants du secondaire.'
                })
            if salaire_fixe:
                cleaned_data['salaire_fixe'] = None  # Effacer le salaire fixe
        else:
            if not salaire_fixe:
                raise ValidationError({
                    'salaire_fixe': f'Le salaire fixe est obligatoire pour les enseignants de type {type_enseignant}.'
                })
            if taux_horaire:
                cleaned_data['taux_horaire'] = None  # Effacer le taux horaire
            cleaned_data['heures_mensuelles'] = None
        
        # Validation des heures mensuelles
        if heures_mensuelles and heures_mensuelles <= 0:
            raise ValidationError({
                'heures_mensuelles': 'Le nombre d\'heures mensuelles doit être supérieur à 0.'
            })
        
        if heures_mensuelles and heures_mensuelles > 200:
            raise ValidationError({
                'heures_mensuelles': 'Le nombre d\'heures mensuelles ne peut pas dépasser 200 heures par mois.'
            })

        if type_enseignant in (
            TypeEnseignant.MATERNELLE,
            TypeEnseignant.PRIMAIRE,
        ) and classes_secondaire:
            self.add_error(
                'classes_secondaire',
                'Utilisez la classe principale pour ce type d’enseignant.',
            )

        if type_enseignant == TypeEnseignant.SECONDAIRE:
            if classe_principale:
                self.add_error(
                    'classe_principale',
                    'Utilisez les affectations du secondaire.',
                )
            classes_ids = {
                classe.pk for classe in (classes_secondaire or ())
            }
            ids_deja_actifs = set()
            if self.instance.pk:
                ids_deja_actifs = set(
                    self.instance.affectations.filter(actif=True)
                    .values_list('classe_id', flat=True)
                )
            if classes_ids - ids_deja_actifs and not heures_affectation:
                self.add_error(
                    'heures_affectation',
                    'Indiquez les heures par semaine pour les nouvelles affectations.',
                )

        return cleaned_data

    def sauvegarder_affectations(self, enseignant):
        """Synchronise les affectations sans jamais effacer l'historique."""
        if not self.is_valid():
            raise ValueError('Le formulaire doit être valide avant les affectations.')
        if not self.data.get(self.add_prefix('gestion_affectations_presente')):
            # Compatibilité avec un ancien formulaire encore ouvert dans un
            # navigateur : ne jamais clôturer ses affectations à son insu.
            return

        aujourd_hui = timezone.localdate()
        date_debut = (
            self.cleaned_data.get('date_embauche')
            if self.est_creation
            else aujourd_hui
        ) or aujourd_hui
        type_enseignant = self.cleaned_data.get('type_enseignant')

        if type_enseignant in (
            TypeEnseignant.MATERNELLE,
            TypeEnseignant.PRIMAIRE,
        ):
            selection = self.cleaned_data.get('classe_principale')
            classes_ids = {selection.pk} if selection else set()
            matiere = ''
            heures = None
        elif type_enseignant == TypeEnseignant.SECONDAIRE:
            selection = self.cleaned_data.get('classes_secondaire') or ()
            classes_ids = {classe.pk for classe in selection}
            matiere = self.cleaned_data.get('matiere_affectation') or ''
            heures = self.cleaned_data.get('heures_affectation')
        else:
            classes_ids = set()
            matiere = ''
            heures = None

        actives = list(
            enseignant.affectations.filter(actif=True).select_related('classe')
        )
        actives_par_classe = {
            affectation.classe_id: affectation for affectation in actives
        }

        for affectation in actives:
            if affectation.classe_id not in classes_ids:
                affectation.actif = False
                affectation.date_fin = max(
                    aujourd_hui,
                    affectation.date_debut,
                )
                affectation.save()

        for classe_id in classes_ids:
            if classe_id in actives_par_classe:
                continue
            affectation, creee = AffectationClasse.objects.get_or_create(
                enseignant=enseignant,
                classe_id=classe_id,
                date_debut=date_debut,
                defaults={
                    'heures_par_semaine': heures,
                    'matiere': matiere,
                    'actif': True,
                },
            )
            if not creee:
                affectation.heures_par_semaine = heures
                affectation.matiere = matiere
                affectation.date_fin = None
                affectation.actif = True
                affectation.save()

    def clean_telephone(self):
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            # Validation basique du format téléphone guinéen
            telephone = telephone.replace(' ', '').replace('-', '')
            if not telephone.startswith('+224') and not telephone.startswith('224'):
                if len(telephone) == 9 and telephone.startswith(('6', '7')):
                    telephone = '+224' + telephone
                else:
                    raise ValidationError('Format de téléphone invalide. Utilisez le format guinéen.')
        return telephone


class HeuresMensuellesPeriodeForm(forms.Form):
    """Formulaire dynamique de saisie globale des heures d'une période."""

    def __init__(
        self,
        *args,
        enseignants,
        initiales=None,
        verrouilles=None,
        pointes=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        initiales = initiales or {}
        verrouilles = set(verrouilles or ())
        pointes = set(pointes or ())
        for enseignant in enseignants:
            nom_champ = f'heures_{enseignant.pk}'
            self.fields[nom_champ] = forms.DecimalField(
                required=False,
                min_value=Decimal('0'),
                max_value=Decimal('744'),
                max_digits=6,
                decimal_places=2,
                label=f'Heures de {enseignant.nom_complet}',
                help_text=(
                    'Les pointages journaliers sont prioritaires.'
                    if enseignant.pk in pointes
                    else "À utiliser uniquement si aucune heure n'a été pointée."
                ),
                widget=forms.NumberInput(attrs={
                    'class': 'form-control form-control-sm',
                    'step': '0.25',
                    'min': '0',
                    'max': '744',
                    'placeholder': 'Pointages',
                }),
                initial=initiales.get(enseignant.pk),
                disabled=(
                    enseignant.pk in verrouilles or enseignant.pk in pointes
                ),
            )

class AffectationClasseForm(forms.ModelForm):
    """Formulaire pour affecter un enseignant à une classe"""

    class Meta:
        model = AffectationClasse
        fields = [
            'classe', 'heures_par_semaine', 'matiere',
            'date_debut', 'date_fin', 'actif'
        ]
        widgets = {
            'classe': forms.Select(attrs={'class': 'form-select'}),
            'heures_par_semaine': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.25', 'min': '0'
            }),
            'matiere': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Mathématiques'}),
            'date_debut': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'date_fin': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'actif': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'classe': 'Classe *',
            'heures_par_semaine': 'Heures par semaine',
            'matiere': 'Matière',
            'date_debut': 'Date de début *',
            'date_fin': 'Date de fin',
            'actif': 'Active',
        }

    def __init__(self, *args, **kwargs):
        # Attendre un paramètre optionnel enseignant pour filtrer les classes
        self.enseignant = kwargs.pop('enseignant', None)
        super().__init__(*args, **kwargs)

        # IMPORTANT: fournir l'enseignant à l'instance dès l'init pour que
        # la validation du modèle (AffectationClasse.clean) puisse y accéder
        # pendant form.is_valid() sans déclencher RelatedObjectDoesNotExist.
        if self.enseignant is not None:
            try:
                self.instance.enseignant = self.enseignant
            except Exception:
                pass

        # Champs requis
        self.fields['classe'].required = True
        self.fields['date_debut'].required = True

        # Restreindre les classes à l'école, au cycle et à l'année récente.
        if self.enseignant and getattr(self.enseignant, 'ecole_id', None):
            classe_existante = (
                (self.instance.classe_id,)
                if self.instance.pk and self.instance.classe_id
                else ()
            )
            self.fields['classe'].queryset = classes_affectables(
                self.enseignant.ecole_id,
                self.enseignant.type_enseignant,
                classe_existante,
            )
        else:
            self.fields['classe'].queryset = Classe.objects.none()

        if not self.is_bound and not self.instance.pk:
            self.fields['date_debut'].initial = timezone.localdate()

    def clean(self):
        cleaned_data = super().clean()
        if not self.enseignant:
            raise ValidationError('Enseignant requis pour créer une affectation.')

        # Validation spécifique aux enseignants du secondaire
        if self.enseignant.type_enseignant == TypeEnseignant.SECONDAIRE:
            if not cleaned_data.get('heures_par_semaine'):
                raise ValidationError({'heures_par_semaine': "Obligatoire pour les enseignants du secondaire."})

        # Vérifier cohérence des dates
        d_debut = cleaned_data.get('date_debut')
        d_fin = cleaned_data.get('date_fin')
        if d_debut and d_fin and d_fin < d_debut:
            raise ValidationError({'date_fin': 'La date de fin ne peut pas être antérieure à la date de début.'})

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.enseignant:
            obj.enseignant = self.enseignant
        if commit:
            obj.save()
        return obj


class PresenceForm(forms.ModelForm):
    """Formulaire pour pointer/modifier une présence"""
    
    class Meta:
        model = PresenceEnseignant
        fields = [
            'enseignant', 'date', 'statut',
            'heure_arrivee', 'heure_depart', 'heures_travaillees',
            'observations', 'justifie'
        ]
        widgets = {
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'statut': forms.Select(attrs={'class': 'form-select'}),
            'heure_arrivee': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heure_depart': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'heures_travaillees': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.25',
                'min': '0',
                'placeholder': 'Calculé automatiquement si vide'
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Motif d\'absence, retard, etc.'
            }),
            'justifie': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'enseignant': 'Enseignant *',
            'date': 'Date *',
            'statut': 'Statut *',
            'heure_arrivee': 'Heure d\'arrivée',
            'heure_depart': 'Heure de départ',
            'heures_travaillees': 'Heures travaillées',
            'observations': 'Observations',
            'justifie': 'Absence/Retard justifié',
        }
    
    def __init__(self, *args, **kwargs):
        ecole = kwargs.pop('ecole', None)
        super().__init__(*args, **kwargs)
        
        # Filtrer les enseignants par école
        if ecole:
            self.fields['enseignant'].queryset = Enseignant.objects.filter(
                ecole=ecole,
                statut='ACTIF'
            ).order_by('nom', 'prenoms')
    
    def clean(self):
        cleaned_data = super().clean()
        heure_arrivee = cleaned_data.get('heure_arrivee')
        heure_depart = cleaned_data.get('heure_depart')
        heures_travaillees = cleaned_data.get('heures_travaillees')
        statut = cleaned_data.get('statut')

        if bool(heure_arrivee) != bool(heure_depart):
            raise ValidationError(
                "L'heure d'arrivée et l'heure de départ doivent être renseignées ensemble."
            )

        if statut in {'PRESENT', 'RETARD'}:
            if not (heure_arrivee and heure_depart) and not (
                heures_travaillees is not None and heures_travaillees > 0
            ):
                raise ValidationError(
                    "Renseignez les heures d'arrivée et de départ, ou le total travaillé."
                )

        if statut in {'ABSENT', 'CONGE', 'MALADIE'}:
            if heure_arrivee or heure_depart or (
                heures_travaillees is not None and heures_travaillees > 0
            ):
                raise ValidationError(
                    'Aucune heure travaillée ne peut être enregistrée pour ce statut.'
                )
        
        return cleaned_data


class EtatSalaireAjustementForm(forms.ModelForm):
    """Modification contrôlée du calcul avant validation définitive."""

    class Meta:
        model = EtatSalaire
        fields = [
            'salaire_base', 'total_heures', 'taux_horaire_applique',
            'primes', 'deductions', 'observations',
        ]
        widgets = {
            'salaire_base': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01'
            }),
            'total_heures': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'max': '744', 'step': '0.25'
            }),
            'taux_horaire_applique': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01'
            }),
            'primes': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01'
            }),
            'deductions': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '0', 'step': '0.01'
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 4,
                'placeholder': 'Motif des primes ou retenues',
            }),
        }

    def __init__(self, *args, heures_pointage=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.heures_pointage = Decimal(heures_pointage or 0)

        if self.instance.enseignant.est_taux_horaire:
            self.fields.pop('salaire_base')
            self.fields['total_heures'].required = True
            self.fields['taux_horaire_applique'].required = True
            if self.heures_pointage > 0:
                self.fields['total_heures'].disabled = True
                self.fields['total_heures'].help_text = (
                    'Valeur calculée automatiquement depuis les pointages journaliers.'
                )
            else:
                self.fields['total_heures'].help_text = (
                    "Saisie manuelle autorisée car aucune heure n'a été pointée."
                )
        else:
            self.fields.pop('total_heures')
            self.fields.pop('taux_horaire_applique')
            self.fields['salaire_base'].required = True

    def clean(self):
        cleaned_data = super().clean()
        primes = cleaned_data.get('primes') or 0
        deductions = cleaned_data.get('deductions') or 0
        if self.instance.enseignant.est_taux_horaire:
            heures = cleaned_data.get('total_heures')
            taux = cleaned_data.get('taux_horaire_applique')
            if heures is None or taux is None:
                salaire_base = Decimal('0')
            else:
                salaire_base = heures * taux
        else:
            salaire_base = cleaned_data.get('salaire_base') or Decimal('0')

        avances = self.instance.avances or 0
        if deductions + avances > salaire_base + primes:
            self.add_error(
                'deductions',
                'Les retenues et les avances ne peuvent pas dépasser '
                'le salaire de base et les primes.',
            )

        return cleaned_data


class AvanceSalaireForm(forms.ModelForm):
    """Création et modification contrôlées d'une avance sur salaire."""

    class Meta:
        model = AvanceSalaire
        fields = [
            'enseignant', 'periode', 'date_avance', 'montant',
            'reference', 'motif',
        ]
        widgets = {
            'enseignant': forms.Select(attrs={'class': 'form-select'}),
            'periode': forms.Select(attrs={'class': 'form-select'}),
            'date_avance': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
            }),
            'montant': forms.NumberInput(attrs={
                'class': 'form-control', 'min': '1', 'step': '1',
                'placeholder': 'Montant versé en GNF',
            }),
            'reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Numéro de reçu ou référence (facultatif)',
            }),
            'motif': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3,
                'placeholder': "Motif ou observation concernant l'avance",
            }),
        }

    def __init__(self, *args, user=None, ecole=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.ecole = ecole

        enseignants = Enseignant.objects.filter(statut=StatutEnseignant.ACTIF)
        periodes = PeriodeSalaire.objects.filter(cloturee=False)
        if ecole is not None:
            enseignants = enseignants.filter(ecole=ecole)
            periodes = periodes.filter(ecole=ecole)

        if self.instance.pk:
            enseignants = Enseignant.objects.filter(
                Q(pk=self.instance.enseignant_id)
                | Q(pk__in=enseignants.values('pk'))
            )
            periodes = PeriodeSalaire.objects.filter(
                Q(pk=self.instance.periode_id)
                | Q(pk__in=periodes.values('pk'))
            )

        self.fields['enseignant'].queryset = enseignants.select_related(
            'ecole'
        ).order_by('nom', 'prenoms')
        self.fields['periode'].queryset = periodes.select_related(
            'ecole'
        ).order_by('-annee', '-mois')
        self.fields['enseignant'].label_from_instance = lambda obj: (
            f"{obj.nom_complet} — {obj.get_type_enseignant_display()}"
        )
        self.fields['date_avance'].initial = (
            self.instance.date_avance if self.instance.pk else timezone.localdate()
        )

    def clean(self):
        cleaned_data = super().clean()
        enseignant = cleaned_data.get('enseignant')
        periode = cleaned_data.get('periode')
        montant = cleaned_data.get('montant')
        date_avance = cleaned_data.get('date_avance')

        if date_avance and date_avance > timezone.localdate():
            self.add_error('date_avance', "La date de l'avance ne peut pas être future.")

        if periode and periode.cloturee:
            self.add_error('periode', "Cette période de salaire est clôturée.")

        if enseignant and periode and enseignant.ecole_id != periode.ecole_id:
            self.add_error(
                'enseignant',
                "L'enseignant et la période doivent appartenir à la même école.",
            )

        if enseignant and periode:
            etat = EtatSalaire.objects.filter(
                enseignant=enseignant,
                periode=periode,
            ).first()
            if etat and (etat.valide or etat.paye):
                self.add_error(
                    'periode',
                    "Le salaire de cet enseignant est déjà validé pour cette période.",
                )
            elif etat and montant:
                autres = AvanceSalaire.objects.filter(
                    enseignant=enseignant,
                    periode=periode,
                    statut=StatutAvanceSalaire.EN_ATTENTE,
                )
                if self.instance.pk:
                    autres = autres.exclude(pk=self.instance.pk)
                total_autres = autres.aggregate(total=Sum('montant'))['total'] or 0
                disponible = (
                    (etat.salaire_base or 0)
                    + (etat.primes or 0)
                    - (etat.deductions or 0)
                )
                if total_autres + montant > disponible:
                    self.add_error(
                        'montant',
                        "Le total des avances dépasse le salaire disponible "
                        f"({disponible:,.0f} GNF).",
                    )

        return cleaned_data


class AnnulationAvanceSalaireForm(forms.Form):
    motif_annulation = forms.CharField(
        label="Motif de l'annulation",
        min_length=3,
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 3,
            'placeholder': "Expliquez pourquoi cette avance est annulée",
        }),
    )
