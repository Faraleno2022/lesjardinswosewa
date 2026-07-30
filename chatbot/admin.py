from django.contrib import admin
from .models import Matiere, DocumentCours, ConversationChat, MessageChat, RecherchePopulaire


@admin.register(Matiere)
class MatiereAdmin(admin.ModelAdmin):
    list_display = ['icone', 'nom', 'actif', 'ordre', 'date_creation']
    list_filter = ['actif']
    search_fields = ['nom', 'description']
    list_editable = ['ordre', 'actif']
    ordering = ['ordre', 'nom']


@admin.register(DocumentCours)
class DocumentCoursAdmin(admin.ModelAdmin):
    list_display = ['titre', 'matiere', 'niveau', 'actif', 'nombre_consultations', 'date_upload']
    list_filter = ['matiere', 'niveau', 'actif', 'date_upload']
    search_fields = ['titre', 'description', 'contenu_extrait']
    readonly_fields = ['nombre_consultations', 'date_upload', 'date_modification']
    list_editable = ['actif']
    date_hierarchy = 'date_upload'
    
    fieldsets = (
        ('Informations', {
            'fields': ('titre', 'description', 'matiere', 'niveau')
        }),
        ('Fichier', {
            'fields': ('fichier', 'contenu_extrait')
        }),
        ('Métadonnées', {
            'fields': ('uploaded_by', 'actif', 'nombre_consultations', 'date_upload', 'date_modification'),
            'classes': ('collapse',)
        }),
    )


@admin.register(ConversationChat)
class ConversationChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'utilisateur', 'matiere', 'active', 'date_debut', 'date_derniere_activite']
    list_filter = ['active', 'matiere', 'date_debut']
    search_fields = ['utilisateur__username', 'session_id']
    readonly_fields = ['date_debut', 'date_derniere_activite']


@admin.register(MessageChat)
class MessageChatAdmin(admin.ModelAdmin):
    list_display = ['id', 'conversation', 'type_message', 'contenu_court', 'date_envoi']
    list_filter = ['type_message', 'date_envoi']
    search_fields = ['contenu']
    readonly_fields = ['date_envoi']
    
    def contenu_court(self, obj):
        return obj.contenu[:50] + '...' if len(obj.contenu) > 50 else obj.contenu
    contenu_court.short_description = 'Contenu'


@admin.register(RecherchePopulaire)
class RecherchePopulaireAdmin(admin.ModelAdmin):
    list_display = ['question', 'matiere', 'nombre_recherches', 'derniere_recherche']
    list_filter = ['matiere', 'derniere_recherche']
    search_fields = ['question']
    ordering = ['-nombre_recherches']
