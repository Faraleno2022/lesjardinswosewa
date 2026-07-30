from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profil


@receiver(post_save, sender=User)
def create_or_update_user_profil(sender, instance: User, created: bool, **kwargs):
    """
    Crée automatiquement un Profil pour tout nouvel utilisateur.
    - Superutilisateur => rôle ADMIN
    - Sinon => rôle COMPTABLE (par défaut, modifiable ensuite dans l'interface)
    Met aussi à jour le Profil existant si besoin (par ex. si rôle manquant).
    """
    try:
        profil, was_created = Profil.objects.get_or_create(user=instance, defaults={
            'role': 'ADMIN' if instance.is_superuser else 'COMPTABLE',
        })
        # Si le profil existait déjà, on peut harmoniser le rôle pour les superusers
        # sans toucher aux autres rôles personnalisés.
        if not was_created and instance.is_superuser and profil.role != 'ADMIN':
            profil.role = 'ADMIN'
            profil.save(update_fields=['role'])
    except Exception:
        # Ne jamais bloquer l'enregistrement d'un utilisateur si problème de profil
        pass
