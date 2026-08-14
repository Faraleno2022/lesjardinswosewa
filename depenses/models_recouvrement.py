"""Modules de recouvrement : entrées, cuisine, documents, versements,
abonnements informatique et salaires du personnel.

Ces modules partagent une structure volontairement simple : une date
renseignée automatiquement, un montant, une observation libre, et un
rattachement à l'école pour le cloisonnement multi-établissements.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from eleves.models import Ecole, Eleve


class OperationRecouvrementBase(models.Model):
    """Socle commun aux opérations de recouvrement.

    La date est posée automatiquement à la création (`editable=False`) :
    l'utilisateur n'a pas à la saisir, conformément au besoin exprimé.
    """

    #: Champ portant l'intitulé principal du module (voir `libelle`).
    CHAMP_LIBELLE = 'designation'

    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, related_name='%(class)ss',
        verbose_name="École",
    )
    date = models.DateField(
        default=timezone.localdate, editable=False, verbose_name="Date",
    )
    montant = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name="Montant (GNF)",
    )
    observation = models.TextField(blank=True, verbose_name="Observation")
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Créé par",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ['-date', '-id']

    @property
    def libelle(self):
        """Intitulé principal de l'opération, quel que soit le module."""
        return getattr(self, self.CHAMP_LIBELLE, '') or ''


class Entree(OperationRecouvrementBase):
    """Toute entrée d'argent dans la caisse, quelle qu'en soit la provenance.

    Registre volontairement large : il recueille les montants encaissés qui ne
    passent pas par un module dédié (dons, subventions, locations, ventes
    diverses...) afin qu'aucune entrée ne reste hors des comptes.
    """

    CHAMP_LIBELLE = 'source'

    TYPE_CHOICES = [
        ('SCOLARITE', 'Scolarité'),
        ('INSCRIPTION', 'Inscription'),
        ('CANTINE', 'Cantine'),
        ('TRANSPORT', 'Transport'),
        ('FOURNITURE', 'Fournitures scolaires'),
        ('INFORMATIQUE', 'Informatique'),
        ('DON', 'Don'),
        ('SUBVENTION', 'Subvention'),
        ('LOCATION', 'Location'),
        ('AUTRE', 'Autre entrée'),
    ]

    MODE_CHOICES = [
        ('ESPECES', 'Espèces'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CHEQUE', 'Chèque'),
        ('VIREMENT', 'Virement bancaire'),
        ('AUTRE', 'Autre'),
    ]

    source = models.CharField(max_length=200, verbose_name="Provenance")
    type_entree = models.CharField(
        max_length=20, choices=TYPE_CHOICES, default='AUTRE',
        verbose_name="Type d'entrée",
    )
    mode_paiement = models.CharField(
        max_length=20, choices=MODE_CHOICES, default='ESPECES',
        verbose_name="Mode d'encaissement",
    )
    reference = models.CharField(
        max_length=50, blank=True, verbose_name="Référence / N° de reçu",
    )

    class Meta(OperationRecouvrementBase.Meta):
        abstract = False
        verbose_name = "Entrée"
        verbose_name_plural = "Entrées"
        indexes = [
            models.Index(fields=['ecole', '-date']),
            models.Index(fields=['ecole', 'type_entree']),
        ]

    def __str__(self):
        return f"{self.source} — {self.montant} GNF ({self.date})"

    @property
    def type_entree_libelle(self):
        return self.get_type_entree_display()

    @property
    def mode_paiement_libelle(self):
        return self.get_mode_paiement_display()


class DepenseCuisine(OperationRecouvrementBase):
    """Dépense engagée pour la cuisine de l'établissement."""

    designation = models.CharField(max_length=200, verbose_name="Désignation")

    class Meta(OperationRecouvrementBase.Meta):
        abstract = False
        verbose_name = "Dépense de cuisine"
        verbose_name_plural = "Dépenses de cuisine"
        indexes = [models.Index(fields=['ecole', '-date'])]

    def __str__(self):
        return f"{self.designation} — {self.montant} GNF ({self.date})"


class DepenseDocument(OperationRecouvrementBase):
    """Dépense liée aux documents administratifs et scolaires."""

    designation = models.CharField(max_length=200, verbose_name="Désignation")

    class Meta(OperationRecouvrementBase.Meta):
        abstract = False
        verbose_name = "Dépense de document"
        verbose_name_plural = "Dépenses de documents"
        indexes = [models.Index(fields=['ecole', '-date'])]

    def __str__(self):
        return f"{self.designation} — {self.montant} GNF ({self.date})"


class Versement(OperationRecouvrementBase):
    """Versement effectué par l'établissement (banque, agence, caisse...)."""

    CHAMP_LIBELLE = 'lieu_versement'

    lieu_versement = models.CharField(max_length=200, verbose_name="Lieu de versement")

    class Meta(OperationRecouvrementBase.Meta):
        abstract = False
        verbose_name = "Versement"
        verbose_name_plural = "Versements"
        indexes = [models.Index(fields=['ecole', '-date'])]

    def __str__(self):
        return f"{self.lieu_versement} — {self.montant} GNF ({self.date})"


class AbonnementInformatique(OperationRecouvrementBase):
    """Abonnement d'un élève aux cours d'informatique, borné dans le temps."""

    SEUIL_ALERTE_JOURS = 15

    eleve = models.ForeignKey(
        Eleve, on_delete=models.CASCADE, related_name='abonnements_informatique',
        verbose_name="Élève",
    )
    date_debut = models.DateField(verbose_name="Début de l'abonnement")
    date_fin = models.DateField(verbose_name="Fin de l'abonnement")

    class Meta(OperationRecouvrementBase.Meta):
        abstract = False
        verbose_name = "Abonnement informatique"
        verbose_name_plural = "Abonnements informatique"
        ordering = ['-date_fin', '-id']
        indexes = [
            models.Index(fields=['ecole', '-date_fin']),
            models.Index(fields=['eleve', '-date_fin']),
        ]

    def __str__(self):
        return f"{self.eleve} — {self.date_debut} au {self.date_fin}"

    @property
    def jours_restants(self):
        """Nombre de jours avant l'échéance ; négatif si déjà expiré."""
        return (self.date_fin - timezone.localdate()).days

    @property
    def statut(self):
        """ACTIF, BIENTOT (échéance proche) ou EXPIRE."""
        restants = self.jours_restants
        if restants < 0:
            return 'EXPIRE'
        if restants <= self.SEUIL_ALERTE_JOURS:
            return 'BIENTOT'
        return 'ACTIF'

    @property
    def statut_libelle(self):
        return {
            'ACTIF': 'Actif',
            'BIENTOT': "Expire bientôt",
            'EXPIRE': 'Expiré',
        }[self.statut]

    @property
    def statut_couleur(self):
        """Classe Bootstrap associée au statut, pour les badges."""
        return {'ACTIF': 'success', 'BIENTOT': 'warning', 'EXPIRE': 'danger'}[self.statut]


# --------------------------------------------------------------------------
# Salaires du personnel : registre autonome du recouvrement
#
# Ce registre est volontairement indépendant du module Salaires (app
# `salaires`) : on y saisit directement un membre du personnel (prénom, nom,
# fonction) puis ses montants mois par mois. Aucun état de salaire, aucune
# période, aucune affectation de classe n'est requis.
# --------------------------------------------------------------------------

class MembrePersonnel(models.Model):
    """Membre du personnel rémunéré, rattaché à l'un des trois groupes suivis."""

    GROUPE_MATERNELLE_PRIMAIRE = 'MATERNELLE_PRIMAIRE'
    GROUPE_COLLEGE = 'COLLEGE'
    GROUPE_DIRECTION = 'DIRECTION'

    GROUPE_CHOICES = [
        (GROUPE_MATERNELLE_PRIMAIRE, 'Maternelle et primaire'),
        (GROUPE_COLLEGE, 'Collège'),
        (GROUPE_DIRECTION, 'Équipe de direction'),
    ]

    ecole = models.ForeignKey(
        Ecole, on_delete=models.CASCADE, related_name='membres_personnel',
        verbose_name="École",
    )
    prenom = models.CharField(max_length=100, verbose_name="Prénom")
    nom = models.CharField(max_length=100, verbose_name="Nom")
    fonction = models.CharField(max_length=120, verbose_name="Fonction")
    groupe = models.CharField(
        max_length=25, choices=GROUPE_CHOICES, default=GROUPE_MATERNELLE_PRIMAIRE,
        verbose_name="Groupe",
    )
    actif = models.BooleanField(default=True, verbose_name="En activité")
    observation = models.TextField(blank=True, verbose_name="Observation")
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+', verbose_name="Créé par",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Membre du personnel"
        verbose_name_plural = "Membres du personnel"
        ordering = ['nom', 'prenom']
        indexes = [models.Index(fields=['ecole', 'groupe'])]

    def __str__(self):
        return f"{self.prenom} {self.nom} — {self.fonction}"

    @property
    def nom_complet(self):
        return f"{self.prenom} {self.nom}".strip()

    @property
    def groupe_libelle(self):
        return self.get_groupe_display()


class SalaireMensuelPersonnel(models.Model):
    """Montant versé à un membre du personnel pour un mois donné.

    Un enregistrement par mois renseigné : un mois laissé vide n'existe pas en
    base, ce qui distingue « rien de saisi » d'un montant volontairement nul.
    """

    membre = models.ForeignKey(
        MembrePersonnel, on_delete=models.CASCADE, related_name='salaires_mensuels',
        verbose_name="Membre du personnel",
    )
    annee = models.PositiveIntegerField(verbose_name="Année")
    mois = models.PositiveSmallIntegerField(verbose_name="Mois")
    montant = models.DecimalField(
        max_digits=12, decimal_places=0, verbose_name="Montant (GNF)",
    )
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Salaire mensuel du personnel"
        verbose_name_plural = "Salaires mensuels du personnel"
        ordering = ['-annee', '-mois']
        constraints = [
            models.UniqueConstraint(
                fields=['membre', 'annee', 'mois'], name='salaire_personnel_unique_mois',
            ),
        ]
        indexes = [models.Index(fields=['annee', 'mois'])]

    def __str__(self):
        return f"{self.membre.nom_complet} — {self.mois}/{self.annee} : {self.montant} GNF"
