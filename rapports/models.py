from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from synchronisation.mixins import SyncTrackedModel

class TypeRapport(SyncTrackedModel):
    """Modèle pour les types de rapports"""
    CATEGORIE_CHOICES = [
        ('FINANCIER', 'Financier'),
        ('PEDAGOGIQUE', 'Pédagogique'),
        ('ADMINISTRATIF', 'Administratif'),
        ('STATISTIQUE', 'Statistique'),
    ]
    
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom du rapport")
    description = models.TextField(verbose_name="Description")
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, verbose_name="Catégorie")
    
    # Configuration du rapport
    template_path = models.CharField(max_length=200, verbose_name="Chemin du template")
    requete_sql = models.TextField(blank=True, null=True, verbose_name="Requête SQL personnalisée")
    parametres_requis = models.JSONField(default=dict, verbose_name="Paramètres requis")
    
    # Permissions
    roles_autorises = models.JSONField(default=list, verbose_name="Rôles autorisés")
    
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Type de rapport"
        verbose_name_plural = "Types de rapports"
        ordering = ['categorie', 'nom']
    
    def __str__(self):
        return f"{self.nom} ({self.get_categorie_display()})"

class Rapport(SyncTrackedModel):
    """Modèle pour les rapports générés"""
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours de génération'),
        ('TERMINE', 'Terminé'),
        ('ERREUR', 'Erreur'),
    ]
    
    FORMAT_CHOICES = [
        ('PDF', 'PDF'),
        ('EXCEL', 'Excel'),
        ('CSV', 'CSV'),
        ('HTML', 'HTML'),
    ]
    
    type_rapport = models.ForeignKey(TypeRapport, on_delete=models.CASCADE, related_name='rapports')
    titre = models.CharField(max_length=200, verbose_name="Titre du rapport")
    
    # Paramètres de génération
    parametres = models.JSONField(default=dict, verbose_name="Paramètres utilisés")
    periode_debut = models.DateField(null=True, blank=True, verbose_name="Début de période")
    periode_fin = models.DateField(null=True, blank=True, verbose_name="Fin de période")
    
    # Informations de génération
    format_rapport = models.CharField(max_length=10, choices=FORMAT_CHOICES, verbose_name="Format")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS', verbose_name="Statut")
    fichier = models.FileField(upload_to='rapports/', blank=True, null=True, verbose_name="Fichier généré")
    
    # Statistiques
    nombre_enregistrements = models.PositiveIntegerField(default=0, verbose_name="Nombre d'enregistrements")
    taille_fichier = models.PositiveIntegerField(default=0, verbose_name="Taille du fichier (bytes)")
    duree_generation = models.DurationField(null=True, blank=True, verbose_name="Durée de génération")
    
    # Messages d'erreur
    message_erreur = models.TextField(blank=True, null=True, verbose_name="Message d'erreur")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_generation = models.DateTimeField(null=True, blank=True, verbose_name="Date de génération")
    genere_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Rapport"
        verbose_name_plural = "Rapports"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.titre} - {self.date_creation.strftime('%d/%m/%Y')}"
    
    @property
    def taille_fichier_lisible(self):
        """Retourne la taille du fichier dans un format lisible"""
        if self.taille_fichier < 1024:
            return f"{self.taille_fichier} B"
        elif self.taille_fichier < 1024 * 1024:
            return f"{self.taille_fichier / 1024:.1f} KB"
        else:
            return f"{self.taille_fichier / (1024 * 1024):.1f} MB"

class TableauBord(SyncTrackedModel):
    """Modèle pour les tableaux de bord personnalisés"""
    nom = models.CharField(max_length=100, verbose_name="Nom du tableau de bord")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    
    # Propriétaire et partage
    proprietaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tableaux_bord')
    partage_avec = models.ManyToManyField(User, blank=True, related_name='tableaux_bord_partages')
    public = models.BooleanField(default=False, verbose_name="Public")
    
    # Configuration
    configuration = models.JSONField(default=dict, verbose_name="Configuration du tableau")
    ordre_widgets = models.JSONField(default=list, verbose_name="Ordre des widgets")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Tableau de bord"
        verbose_name_plural = "Tableaux de bord"
        ordering = ['nom']
    
    def __str__(self):
        return self.nom

class Widget(SyncTrackedModel):
    """Modèle pour les widgets des tableaux de bord"""
    TYPE_CHOICES = [
        ('GRAPHIQUE_LIGNE', 'Graphique en ligne'),
        ('GRAPHIQUE_BARRE', 'Graphique en barres'),
        ('GRAPHIQUE_SECTEUR', 'Graphique en secteurs'),
        ('TABLEAU', 'Tableau'),
        ('INDICATEUR', 'Indicateur'),
        ('JAUGE', 'Jauge'),
        ('LISTE', 'Liste'),
    ]
    
    tableau_bord = models.ForeignKey(TableauBord, on_delete=models.CASCADE, related_name='widgets')
    nom = models.CharField(max_length=100, verbose_name="Nom du widget")
    type_widget = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type de widget")
    
    # Configuration
    titre = models.CharField(max_length=200, verbose_name="Titre affiché")
    requete_sql = models.TextField(verbose_name="Requête SQL")
    configuration = models.JSONField(default=dict, verbose_name="Configuration du widget")
    
    # Position et taille
    position_x = models.PositiveIntegerField(default=0, verbose_name="Position X")
    position_y = models.PositiveIntegerField(default=0, verbose_name="Position Y")
    largeur = models.PositiveIntegerField(default=4, verbose_name="Largeur (colonnes)")
    hauteur = models.PositiveIntegerField(default=3, verbose_name="Hauteur (lignes)")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Widget"
        verbose_name_plural = "Widgets"
        ordering = ['tableau_bord', 'position_y', 'position_x']
    
    def __str__(self):
        return f"{self.tableau_bord.nom} - {self.nom}"

class ExportProgramme(SyncTrackedModel):
    """Modèle pour les exports programmés"""
    FREQUENCE_CHOICES = [
        ('QUOTIDIEN', 'Quotidien'),
        ('HEBDOMADAIRE', 'Hebdomadaire'),
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('ANNUEL', 'Annuel'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('TERMINE', 'Terminé'),
    ]
    
    nom = models.CharField(max_length=100, verbose_name="Nom de l'export")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    type_rapport = models.ForeignKey(TypeRapport, on_delete=models.CASCADE, related_name='exports_programmes')
    
    # Configuration de la programmation
    frequence = models.CharField(max_length=20, choices=FREQUENCE_CHOICES, verbose_name="Fréquence")
    heure_execution = models.TimeField(verbose_name="Heure d'exécution")
    jour_semaine = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Jour de la semaine (1=Lundi)",
        help_text="Pour les exports hebdomadaires"
    )
    jour_mois = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Jour du mois",
        help_text="Pour les exports mensuels"
    )
    
    # Destinataires
    emails_destinataires = models.JSONField(default=list, verbose_name="Emails des destinataires")
    
    # Paramètres du rapport
    parametres = models.JSONField(default=dict, verbose_name="Paramètres du rapport")
    format_export = models.CharField(max_length=10, choices=Rapport.FORMAT_CHOICES, verbose_name="Format d'export")
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut")
    derniere_execution = models.DateTimeField(null=True, blank=True, verbose_name="Dernière exécution")
    prochaine_execution = models.DateTimeField(null=True, blank=True, verbose_name="Prochaine exécution")
    
    # Métadonnées
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Export programmé"
        verbose_name_plural = "Exports programmés"
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.nom} - {self.get_frequence_display()}"
