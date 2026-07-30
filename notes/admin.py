from django.contrib import admin
from .models import NoteSuivi, Devoir, RemiseDevoir, CreneauEmploiDuTemps
from .models import ClasseNote, MatiereNote, Evaluation, NoteEleve, NoteMensuelle, CompositionNote, AppreciationMaternelle, ThemeBulletin, ActiviteJournaliere, PieceJointeActivite

@admin.register(ClasseNote)
class ClasseNoteAdmin(admin.ModelAdmin):
    list_display = ['nom', 'niveau', 'annee_scolaire', 'effectif', 'actif', 'ecole', 'date_creation']
    list_filter = ['niveau', 'actif', 'annee_scolaire', 'ecole']
    search_fields = ['nom', 'description']
    ordering = ['niveau', 'nom']
    readonly_fields = ['date_creation', 'date_modification', 'cree_par']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('ecole', 'nom', 'niveau', 'annee_scolaire')
        }),
        ('Détails', {
            'fields': ('effectif', 'description', 'actif')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

@admin.register(MatiereNote)
class MatiereNoteAdmin(admin.ModelAdmin):
    list_display = ['nom', 'code', 'classe', 'coefficient', 'actif', 'date_creation']
    list_filter = ['actif', 'classe']
    search_fields = ['nom', 'code']
    ordering = ['classe', 'nom']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

@admin.register(Evaluation)
class EvaluationAdmin(admin.ModelAdmin):
    list_display = ['titre', 'matiere', 'type_evaluation', 'periode', 'date_evaluation', 'note_sur', 'coefficient']
    list_filter = ['type_evaluation', 'periode', 'matiere__classe']
    search_fields = ['titre', 'matiere__nom']
    ordering = ['-date_evaluation']
    date_hierarchy = 'date_evaluation'
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)

@admin.register(NoteEleve)
class NoteEleveAdmin(admin.ModelAdmin):
    list_display = ['eleve', 'evaluation', 'note', 'absent', 'date_creation']
    list_filter = ['absent', 'evaluation__matiere__classe', 'evaluation__periode']
    search_fields = ['eleve__nom', 'eleve__prenom', 'evaluation__titre']
    ordering = ['evaluation', 'eleve__nom']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(NoteMensuelle)
class NoteMensuelleAdmin(admin.ModelAdmin):
    list_display = ['eleve', 'matiere', 'mois', 'note', 'absent', 'annee_scolaire', 'date_creation']
    list_filter = ['mois', 'absent', 'annee_scolaire', 'matiere__classe']
    search_fields = ['eleve__nom', 'eleve__prenom', 'matiere__nom']
    ordering = ['eleve', 'matiere', 'mois']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('eleve', 'matiere', 'mois', 'annee_scolaire')
        }),
        ('Note', {
            'fields': ('note', 'absent')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['date_creation', 'date_modification', 'cree_par']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(CompositionNote)
class CompositionNoteAdmin(admin.ModelAdmin):
    list_display = ['eleve', 'matiere', 'periode', 'note', 'absent', 'annee_scolaire', 'date_creation']
    list_filter = ['periode', 'absent', 'annee_scolaire', 'matiere__classe']
    search_fields = ['eleve__nom', 'eleve__prenom', 'matiere__nom']
    ordering = ['eleve', 'matiere', 'periode']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('eleve', 'matiere', 'periode', 'annee_scolaire')
        }),
        ('Note', {
            'fields': ('note', 'absent')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['date_creation', 'date_modification', 'cree_par']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(AppreciationMaternelle)
class AppreciationMaternelleAdmin(admin.ModelAdmin):
    list_display = ['eleve', 'matiere', 'trimestre', 'appreciation', 'absent', 'annee_scolaire', 'date_creation']
    list_filter = ['trimestre', 'appreciation', 'absent', 'annee_scolaire', 'matiere__classe']
    search_fields = ['eleve__nom', 'eleve__prenom', 'matiere__nom']
    ordering = ['eleve', 'matiere', 'trimestre']
    
    fieldsets = (
        ('Informations de base', {
            'fields': ('eleve', 'matiere', 'trimestre', 'annee_scolaire')
        }),
        ('Appréciation', {
            'fields': ('appreciation', 'commentaire', 'absent')
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    readonly_fields = ['date_creation', 'date_modification', 'cree_par']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


@admin.register(ThemeBulletin)
class ThemeBulletinAdmin(admin.ModelAdmin):
    list_display = ['nom', 'ecole', 'actif', 'par_defaut', 'date_creation']
    list_filter = ['actif', 'par_defaut', 'ecole']
    search_fields = ['nom']
    ordering = ['-par_defaut', '-actif', 'nom']
    readonly_fields = ['date_creation', 'date_modification', 'cree_par']
    
    fieldsets = (
        ('Informations générales', {
            'fields': ('nom', 'ecole', 'actif', 'par_defaut')
        }),
        ('Couleurs principales', {
            'fields': ('couleur_primaire', 'couleur_secondaire', 'couleur_accent'),
            'description': 'Couleurs principales utilisées dans le bulletin'
        }),
        ('Couleurs de texte', {
            'fields': ('couleur_texte_principal', 'couleur_texte_secondaire'),
            'classes': ('collapse',)
        }),
        ('Couleurs de fond', {
            'fields': ('couleur_fond_header', 'couleur_fond_tableau', 'couleur_fond_carte'),
            'classes': ('collapse',)
        }),
        ('Couleurs des bordures', {
            'fields': ('couleur_bordure',),
            'classes': ('collapse',)
        }),
        ('Couleurs des mentions', {
            'fields': (
                'couleur_mention_tb',
                'couleur_mention_bien',
                'couleur_mention_ab',
                'couleur_mention_passable',
                'couleur_mention_insuffisant'
            ),
            'classes': ('collapse',),
            'description': 'Couleurs pour chaque type de mention'
        }),
        ('Métadonnées', {
            'fields': ('cree_par', 'date_creation', 'date_modification'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.cree_par = request.user
        super().save_model(request, obj, form, change)


class PieceJointeInline(admin.TabularInline):
    model = PieceJointeActivite
    extra = 1


@admin.register(ActiviteJournaliere)
class ActiviteJournaliereAdmin(admin.ModelAdmin):
    list_display = ['titre', 'type_activite', 'eleve', 'classe', 'date', 'appreciation', 'date_creation']
    list_filter = ['type_activite', 'date', 'classe']
    search_fields = ['titre', 'eleve__nom', 'eleve__prenom']
    date_hierarchy = 'date'
    inlines = [PieceJointeInline]


@admin.register(NoteSuivi)
class NoteSuiviAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'matiere', 'mois', 'type_note', 'note', 'annee_scolaire')
    list_filter = ('type_note', 'mois', 'annee_scolaire')
    search_fields = ('eleve__nom', 'eleve__prenom', 'eleve__matricule', 'matiere__nom')
    raw_id_fields = ('eleve', 'matiere')


@admin.register(Devoir)
class DevoirAdmin(admin.ModelAdmin):
    list_display = ('titre', 'classe', 'matiere', 'date_donne', 'date_remise', 'compte_bonus')
    list_filter = ('classe', 'matiere', 'date_remise', 'compte_bonus')
    search_fields = ('titre',)
    raw_id_fields = ('classe', 'matiere')


@admin.register(RemiseDevoir)
class RemiseDevoirAdmin(admin.ModelAdmin):
    list_display = ('eleve', 'devoir', 'statut', 'note')
    list_filter = ('statut',)
    search_fields = ('eleve__nom', 'eleve__prenom', 'devoir__titre')
    raw_id_fields = ('devoir', 'eleve')


@admin.register(CreneauEmploiDuTemps)
class CreneauEmploiDuTempsAdmin(admin.ModelAdmin):
    list_display = ('classe', 'jour', 'heure_debut', 'heure_fin', 'matiere', 'enseignant', 'salle')
    list_filter = ('jour', 'classe')
    search_fields = ('classe__nom', 'matiere__nom', 'libelle')
    raw_id_fields = ('classe', 'matiere', 'enseignant')
