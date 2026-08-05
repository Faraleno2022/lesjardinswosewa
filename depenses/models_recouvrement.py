"""Modules de recouvrement : cuisine, documents, versements et abonnements informatique.

Ces quatre modules partagent une structure volontairement simple : une date
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
