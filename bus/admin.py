from django.contrib import admin
from .models import AbonnementBus, AbonnementCantine

@admin.register(AbonnementBus)
class AbonnementBusAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'montant', 'reference_externe', 'periodicite', 'date_debut', 'date_expiration', 'statut', 'zone', 'point_arret')
    list_editable = ('periodicite', 'statut')
    list_filter = ('statut', 'periodicite', 'zone', 'eleve__classe__ecole', 'eleve__classe')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule', 'reference_externe', 'zone', 'point_arret', 'contact_parent')
    autocomplete_fields = ('eleve',)
    list_select_related = ('eleve', 'eleve__classe', 'eleve__classe__ecole')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date_debut'
    save_on_top = True
    radio_fields = {
        'periodicite': admin.HORIZONTAL,
        'statut': admin.HORIZONTAL,
    }

    fieldsets = (
        ('Élève', {
            'fields': ('eleve', 'contact_parent'),
        }),
        ('Paiement personnalisable', {
            'fields': (
                'periodicite', 'montant', 'reference_externe',
                'date_debut', 'date_expiration', 'statut',
            ),
            'description': "Le type Annuel peut être choisi ici, puis le montant peut être adapté à l'élève.",
        }),
        ('Transport', {
            'fields': ('zone', 'itineraire', 'point_arret'),
        }),
        ('Alertes', {
            'fields': ('alerte_avant_jours', 'derniere_relance'),
        }),
        ('Observations et métadonnées', {
            'fields': ('observations', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(AbonnementCantine)
class AbonnementCantineAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'type_repas', 'montant', 'reference_externe', 'periodicite', 'date_debut', 'date_expiration', 'statut', 'jours_restants')
    list_editable = ('type_repas', 'periodicite', 'statut')
    list_filter = ('statut', 'periodicite', 'type_repas', 'regime_alimentaire', 'eleve__classe__ecole', 'eleve__classe')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule', 'reference_externe', 'contact_parent', 'regime_alimentaire')
    autocomplete_fields = ('eleve',)
    list_select_related = ('eleve', 'eleve__classe', 'eleve__classe__ecole')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'date_debut'
    save_on_top = True
    radio_fields = {
        'periodicite': admin.HORIZONTAL,
        'type_repas': admin.HORIZONTAL,
        'statut': admin.HORIZONTAL,
    }
    
    fieldsets = (
        ('Informations Élève', {
            'fields': ('eleve', 'contact_parent')
        }),
        ('Paiement et repas personnalisables', {
            'fields': (
                'montant', 'reference_externe', 'periodicite', 'type_repas',
                'date_debut', 'date_expiration', 'statut',
            ),
            'description': "Le paiement Annuel et les services de repas de 10 h ou 14 h peuvent être choisis et modifiés ici.",
        }),
        ('Régime Alimentaire', {
            'fields': ('regime_alimentaire', 'allergies'),
            'classes': ('collapse',)
        }),
        ('Alertes', {
            'fields': ('alerte_avant_jours', 'derniere_relance')
        }),
        ('Observations', {
            'fields': ('observations',),
            'classes': ('collapse',)
        }),
        ('Métadonnées', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
