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


class VersionApplication(models.Model):
    """
    Une version de l'application Windows mise a disposition des postes.

    Le poste n'apprend l'existence d'une mise a jour que par cette table : tant
    qu'une ligne n'est pas publiee, elle reste invisible. C'est ce qui permet
    de preparer une version, de la tester, puis de la diffuser au moment voulu
    sans rien reinstaller a la main sur chaque machine.

    L'empreinte est obligatoire, et c'est le point important : le poste
    telecharge un executable et va le lancer. Sans empreinte verifiee, un
    fichier corrompu en cours de route — ou substitue — s'installerait sans que
    rien ne l'arrete.
    """

    version = models.CharField(
        max_length=20, unique=True,
        help_text="Numero de version, par exemple 1.3.0",
    )
    url_telechargement = models.URLField(
        max_length=500,
        help_text="Adresse HTTPS de l'installateur (.exe). "
                  "Par exemple une publication GitHub.",
    )
    sha256 = models.CharField(
        max_length=64,
        help_text="Empreinte SHA-256 du fichier. "
                  "Sous Windows : certutil -hashfile installateur.exe SHA256",
    )
    taille_octets = models.BigIntegerField(
        null=True, blank=True,
        help_text="Taille attendue du fichier. Facultatif.",
    )
    notes = models.TextField(
        blank=True, help_text="Ce que cette version apporte, en clair.",
    )
    obligatoire = models.BooleanField(
        default=False,
        help_text="Installer sans attendre l'accord de l'utilisateur.",
    )
    publiee = models.BooleanField(
        default=False, db_index=True,
        help_text="Tant que cette case est decochee, aucun poste ne voit "
                  "cette version.",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_publication = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Version de l\'application'
        verbose_name_plural = 'Versions de l\'application'
        ordering = ['-date_creation']

    def __str__(self):
        etat = 'publiee' if self.publiee else 'brouillon'
        return f'MySchoolGN {self.version} ({etat})'

    def clean(self):
        from django.core.exceptions import ValidationError

        erreurs = {}

        empreinte = (self.sha256 or '').strip().lower()
        if len(empreinte) != 64 or any(c not in '0123456789abcdef' for c in empreinte):
            erreurs['sha256'] = (
                "L'empreinte doit compter 64 caracteres hexadecimaux."
            )
        else:
            self.sha256 = empreinte

        # Le fichier est execute sur le poste apres telechargement : le
        # transport doit etre authentifie, sinon l'empreinte elle-meme
        # pourrait etre servie par le meme intermediaire que le fichier.
        if not (self.url_telechargement or '').lower().startswith('https://'):
            erreurs['url_telechargement'] = "L'adresse doit commencer par https://"

        from ecole_moderne.version import numero_de_version
        if numero_de_version(self.version) == (0, 0, 0):
            erreurs['version'] = "Numero de version illisible, par exemple 1.3.0"

        if erreurs:
            raise ValidationError(erreurs)

    def save(self, *args, **kwargs):
        if self.publiee and not self.date_publication:
            self.date_publication = timezone.now()
        super().save(*args, **kwargs)

    @classmethod
    def derniere_publiee(cls):
        """
        La version publiee la plus haute, pas la plus recemment saisie.

        Republier un correctif ancien ne doit pas faire redescendre les postes
        d'une version.
        """
        from ecole_moderne.version import numero_de_version

        publiees = list(cls.objects.filter(publiee=True))
        if not publiees:
            return None
        return max(publiees, key=lambda v: numero_de_version(v.version))
