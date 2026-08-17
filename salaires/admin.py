from django.contrib import admin
from .models import (
    Enseignant, TypeEnseignant, StatutEnseignant, 
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
