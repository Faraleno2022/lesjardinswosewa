from django.db import models
from django.contrib.auth import get_user_model
from eleves.models import Eleve
from decimal import Decimal
from synchronisation.mixins import SyncTrackedModel

User = get_user_model()


class TypeAbonnement(SyncTrackedModel):
    """Types d'abonnements (Bus, Cantine, etc.)"""
    NOM_CHOICES = [
        ('BUS', 'Transport Scolaire'),
        ('CANTINE', 'Cantine'),
        ('GARDERIE', 'Garderie'),
        ('ETUDE', 'Étude Surveillée'),
    ]
    
    nom = models.CharField(max_length=50, choices=NOM_CHOICES, unique=True, verbose_name="Type")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    tarif_mensuel = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Tarif mensuel (GNF)"
    )
    tarif_trimestriel = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Tarif trimestriel (GNF)"
    )
    tarif_annuel = models.DecimalField(
        max_digits=10, decimal_places=0, default=Decimal('0'),
        verbose_name="Tarif annuel (GNF)"
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Type d'abonnement"
        verbose_name_plural = "Types d'abonnements"
        ordering = ['nom']
    
    def __str__(self):
        return self.get_nom_display()


class Itineraire(SyncTrackedModel):
    """Itinéraires de bus"""
    nom = models.CharField(max_length=100, verbose_name="Nom de l'itinéraire")
    description = models.TextField(blank=True, null=True, verbose_name="Description")
    quartiers = models.TextField(
        help_text="Liste des quartiers desservis (un par ligne)",
        verbose_name="Quartiers desservis"
    )
    heure_depart_matin = models.TimeField(verbose_name="Heure départ matin")
    heure_retour_soir = models.TimeField(verbose_name="Heure retour soir")
    capacite = models.IntegerField(default=40, verbose_name="Capacité")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Itinéraire"
        verbose_name_plural = "Itinéraires"
        ordering = ['nom']
    
    def __str__(self):
        return self.nom
    
    def get_quartiers_list(self):
        """Retourne la liste des quartiers"""
        return [q.strip() for q in self.quartiers.split('\n') if q.strip()]
    
    def nombre_abonnes(self):
        """Nombre d'abonnés actifs sur cet itinéraire"""
        return self.abonnementbus_set.filter(statut='ACTIF').count()


class MenuCantine(SyncTrackedModel):
    """Menus de la cantine"""
    JOUR_CHOICES = [
        ('LUNDI', 'Lundi'),
        ('MARDI', 'Mardi'),
        ('MERCREDI', 'Mercredi'),
        ('JEUDI', 'Jeudi'),
        ('VENDREDI', 'Vendredi'),
        ('SAMEDI', 'Samedi'),
    ]
    
    jour = models.CharField(max_length=20, choices=JOUR_CHOICES, verbose_name="Jour")
    semaine = models.IntegerField(verbose_name="Numéro de semaine")
    entree = models.CharField(max_length=200, verbose_name="Entrée")
    plat_principal = models.CharField(max_length=200, verbose_name="Plat principal")
    accompagnement = models.CharField(max_length=200, verbose_name="Accompagnement")
    dessert = models.CharField(max_length=200, verbose_name="Dessert")
    boisson = models.CharField(max_length=100, default="Eau", verbose_name="Boisson")
    date_menu = models.DateField(verbose_name="Date du menu")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    
    class Meta:
        verbose_name = "Menu cantine"
        verbose_name_plural = "Menus cantine"
        ordering = ['-date_menu', 'jour']
        unique_together = ['jour', 'semaine', 'date_menu']
    
    def __str__(self):
        return f"{self.get_jour_display()} - Semaine {self.semaine}"


class Abonnement(SyncTrackedModel):
    """Modèle de base pour les abonnements"""
    DUREE_CHOICES = [
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('ANNUEL', 'Annuel'),
    ]
    
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXPIRE', 'Expiré'),
        ('RESILIE', 'Résilié'),
    ]
    
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, verbose_name="Élève")
    type_abonnement = models.ForeignKey(
        TypeAbonnement, on_delete=models.PROTECT, verbose_name="Type"
    )
    duree = models.CharField(max_length=20, choices=DUREE_CHOICES, verbose_name="Durée")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    montant = models.DecimalField(
        max_digits=10, decimal_places=0, verbose_name="Montant (GNF)"
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut"
    )
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='abonnements_crees'
    )
    
    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.type_abonnement}"
    
    def est_actif(self):
        """Vérifie si l'abonnement est actif"""
        from django.utils import timezone
        today = timezone.now().date()
        return (
            self.statut == 'ACTIF' and 
            self.date_debut <= today <= self.date_fin
        )


class AbonnementBus(SyncTrackedModel):
    """Abonnement spécifique au transport scolaire"""
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXPIRE', 'Expiré'),
        ('RESILIE', 'Résilié'),
    ]
    
    DUREE_CHOICES = [
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('ANNUEL', 'Annuel'),
    ]
    
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, verbose_name="Élève")
    itineraire = models.ForeignKey(
        Itineraire, on_delete=models.PROTECT, verbose_name="Itinéraire"
    )
    duree = models.CharField(max_length=20, choices=DUREE_CHOICES, verbose_name="Durée")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    montant = models.DecimalField(
        max_digits=10, decimal_places=0, verbose_name="Montant (GNF)"
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut"
    )
    point_montee = models.CharField(max_length=200, verbose_name="Point de montée")
    point_descente = models.CharField(max_length=200, verbose_name="Point de descente")
    contact_urgence = models.CharField(
        max_length=20, verbose_name="Contact d'urgence"
    )
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='abonnements_bus_crees'
    )
    
    class Meta:
        verbose_name = "Abonnement bus"
        verbose_name_plural = "Abonnements bus"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.itineraire.nom}"
    
    def est_actif(self):
        """Vérifie si l'abonnement est actif"""
        from django.utils import timezone
        today = timezone.now().date()
        return (
            self.statut == 'ACTIF' and 
            self.date_debut <= today <= self.date_fin
        )


class AbonnementCantine(SyncTrackedModel):
    """Abonnement spécifique à la cantine"""
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('SUSPENDU', 'Suspendu'),
        ('EXPIRE', 'Expiré'),
        ('RESILIE', 'Résilié'),
    ]
    
    DUREE_CHOICES = [
        ('MENSUEL', 'Mensuel'),
        ('TRIMESTRIEL', 'Trimestriel'),
        ('ANNUEL', 'Annuel'),
    ]
    
    REGIME_CHOICES = [
        ('NORMAL', 'Normal'),
        ('VEGETARIEN', 'Végétarien'),
        ('SANS_PORC', 'Sans porc'),
        ('SANS_GLUTEN', 'Sans gluten'),
        ('ALLERGIE', 'Régime spécial (allergie)'),
    ]
    
    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, verbose_name="Élève")
    duree = models.CharField(max_length=20, choices=DUREE_CHOICES, verbose_name="Durée")
    date_debut = models.DateField(verbose_name="Date de début")
    date_fin = models.DateField(verbose_name="Date de fin")
    montant = models.DecimalField(
        max_digits=10, decimal_places=0, verbose_name="Montant (GNF)"
    )
    statut = models.CharField(
        max_length=20, choices=STATUT_CHOICES, default='ACTIF', verbose_name="Statut"
    )
    regime_alimentaire = models.CharField(
        max_length=20, choices=REGIME_CHOICES, default='NORMAL',
        verbose_name="Régime alimentaire"
    )
    allergies = models.TextField(
        blank=True, null=True,
        verbose_name="Allergies alimentaires",
        help_text="Précisez les allergies ou intolérances"
    )
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    cree_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='abonnements_cantine_crees'
    )
    
    class Meta:
        verbose_name = "Abonnement cantine"
        verbose_name_plural = "Abonnements cantine"
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.eleve.nom_complet} - Cantine"
    
    def est_actif(self):
        """Vérifie si l'abonnement est actif"""
        from django.utils import timezone
        today = timezone.now().date()
        return (
            self.statut == 'ACTIF' and 
            self.date_debut <= today <= self.date_fin
        )


class PresenceCantine(SyncTrackedModel):
    """Suivi des présences à la cantine"""
    abonnement = models.ForeignKey(
        AbonnementCantine, on_delete=models.CASCADE, verbose_name="Abonnement"
    )
    date = models.DateField(verbose_name="Date")
    present = models.BooleanField(default=True, verbose_name="Présent")
    menu = models.ForeignKey(
        MenuCantine, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Menu"
    )
    observations = models.TextField(blank=True, null=True, verbose_name="Observations")
    enregistre_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True
    )
    date_enregistrement = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Présence cantine"
        verbose_name_plural = "Présences cantine"
        ordering = ['-date']
        unique_together = ['abonnement', 'date']
    
    def __str__(self):
        return f"{self.abonnement.eleve.nom_complet} - {self.date}"
