from django.contrib import admin

from .models import PresenceJournaliere


@admin.register(PresenceJournaliere)
class PresenceJournaliereAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'classe', 'date', 'statut', 'motif')
    list_filter = ('statut', 'date', 'classe')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule')
    date_hierarchy = 'date'
    raw_id_fields = ('eleve', 'classe')
