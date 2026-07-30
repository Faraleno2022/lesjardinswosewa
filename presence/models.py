from django.db import models
from django.contrib.auth.models import User

from eleves.models import Eleve, Classe
from synchronisation.mixins import SyncTrackedModel


class PresenceJournaliere(SyncTrackedModel):
    """Pointage journalier d'un élève (un enregistrement par élève et par jour)."""

    STATUT_CHOICES = [
        ('PRESENT', 'Présent'),
        ('ABSENT', 'Absent'),
        ('RETARD', 'En retard'),
        ('JUSTIFIE', 'Absence justifiée'),
    ]

    # Statuts comptés comme une absence pour les alertes d'absences consécutives.
    STATUTS_ABSENCE = ('ABSENT',)

    eleve = models.ForeignKey(Eleve, on_delete=models.CASCADE, related_name='presences')
    classe = models.ForeignKey(Classe, on_delete=models.CASCADE, related_name='presences')
    date = models.DateField(verbose_name="Date du pointage", db_index=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='PRESENT')
    motif = models.CharField(max_length=200, blank=True, verbose_name="Motif / observation")

    cree_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='pointages_crees')
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Présence journalière"
        verbose_name_plural = "Présences journalières"
        ordering = ['-date', 'eleve__nom', 'eleve__prenom']
        constraints = [
            models.UniqueConstraint(fields=['eleve', 'date'], name='unique_presence_eleve_date'),
        ]
        indexes = [
            models.Index(fields=['classe', 'date']),
            models.Index(fields=['date', 'statut']),
            models.Index(fields=['eleve', 'date']),
        ]

    def __str__(self):
        return f"{self.eleve.nom_complet} - {self.date} - {self.get_statut_display()}"

    @property
    def est_absence(self):
        return self.statut in self.STATUTS_ABSENCE
