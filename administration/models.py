from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

try:
    from django.db.models import JSONField
except ImportError:
    from django.contrib.postgres.fields import JSONField

User = get_user_model()


class SystemLog(models.Model):
    """Journal des actions administratives importantes"""
    
    ACTION_CHOICES = [
        ('DELETE', 'Suppression'),
        ('SUPPRESSION_DEFINITIVE', 'Suppression définitive'),
        ('RESET', 'Réinitialisation'),
        ('BACKUP', 'Sauvegarde'),
        ('RESTORE', 'Restauration'),
        ('LOGIN', 'Connexion admin'),
        ('ERROR', 'Erreur système'),
    ]
    
    action = models.CharField(max_length=30, choices=ACTION_CHOICES, db_index=True)
    description = models.TextField()
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    details = JSONField(default=dict, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Log système'
        verbose_name_plural = 'Logs système'
    
    def __str__(self):
        return f"{self.action} - {self.timestamp.strftime('%d/%m/%Y %H:%M')} - {self.user or 'Système'}"


class MaintenanceMode(models.Model):
    """Mode maintenance du système"""
    
    is_active = models.BooleanField(default=False)
    message = models.TextField(
        default="Le système est en maintenance. Veuillez réessayer plus tard.",
        help_text="Message affiché aux utilisateurs"
    )
    allowed_users = models.ManyToManyField(
        User, 
        blank=True,
        help_text="Utilisateurs autorisés pendant la maintenance"
    )
    activated_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='maintenance_activated'
    )
    activated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Mode maintenance'
        verbose_name_plural = 'Mode maintenance'
    
    def __str__(self):
        status = "Actif" if self.is_active else "Inactif"
        return f"Mode maintenance - {status}"
    
    def save(self, *args, **kwargs):
        if self.is_active and not self.activated_at:
            self.activated_at = timezone.now()
        super().save(*args, **kwargs)
