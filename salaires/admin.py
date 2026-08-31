from django.contrib import admin
from .models import (
    Enseignant, TypeEnseignant, StatutEnseignant,
    AvanceSalaire, StatutAvanceSalaire,
    AffectationClasse, PeriodeSalaire, EtatSalaire, 
    DetailHeuresClasse, PresenceEnseignant, SaisieHeuresMensuelles
)


@admin.register(PresenceEnseignant)
class PresenceEnseignantAdmin(admin.ModelAdmin):
    list_display = ['enseignant', 'date', 'statut', 'heure_arrivee', 'heure_depart', 'heures_travaillees', 'justifie']
    list_filter = ['statut', 'date', 'justifie', 'enseignant__ecole']
    search_fields = ['enseignant__nom', 'enseignant__prenoms', 'observations']
    date_hierarchy = 'date'
    ordering = ['-date', 'enseignant__nom']
    
    fieldsets = (
        ('Informations principales', {
            'fields': ('enseignant', 'date', 'statut')
        }),
        ('Heures', {
            'fields': ('heure_arrivee', 'heure_depart', 'heures_travaillees')
        }),
        ('Détails', {
            'fields': ('observations', 'justifie')
        }),
        ('Métadonnées', {
            'fields': ('pointe_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['date_creation', 'date_modification']
    
    def save_model(self, request, obj, form, change):
        if not change:  # Nouveau pointage
            obj.pointe_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(SaisieHeuresMensuelles)
class SaisieHeuresMensuellesAdmin(admin.ModelAdmin):
    list_display = ['enseignant', 'periode', 'heures', 'saisi_par', 'date_modification']
    list_filter = ['periode__annee', 'periode__mois', 'periode__ecole']
    search_fields = ['enseignant__nom', 'enseignant__prenoms']
    raw_id_fields = ['enseignant', 'periode', 'saisi_par']


@admin.register(AvanceSalaire)
class AvanceSalaireAdmin(admin.ModelAdmin):
    list_display = [
        'enseignant', 'periode', 'date_avance', 'montant',
        'reference', 'statut', 'cree_par',
    ]
    list_filter = [
        'statut', 'periode__annee', 'periode__mois',
        'enseignant__ecole', 'date_avance',
    ]
    search_fields = [
        'enseignant__nom', 'enseignant__prenoms', 'reference',
        'motif', 'motif_annulation',
    ]
    raw_id_fields = [
        'enseignant', 'periode', 'etat_salaire', 'cree_par', 'annulee_par',
    ]
    readonly_fields = [
        'date_creation', 'date_modification', 'date_annulation',
    ]
    date_hierarchy = 'date_avance'

    def has_delete_permission(self, request, obj=None):
        # Une erreur se corrige par annulation afin de conserver la trace.
        return False

    def get_readonly_fields(self, request, obj=None):
        champs = list(super().get_readonly_fields(request, obj))
        if obj and obj.statut != StatutAvanceSalaire.EN_ATTENTE:
            champs.extend([
                'enseignant', 'periode', 'date_avance', 'montant',
                'reference', 'motif', 'statut', 'etat_salaire',
                'cree_par', 'annulee_par', 'motif_annulation',
            ])
        return champs

    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)
