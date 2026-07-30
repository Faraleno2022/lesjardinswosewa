from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import SystemLog
from .views import log_admin_action

User = get_user_model()


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Enregistre les connexions des administrateurs"""
    if user.is_staff or user.is_superuser:
        try:
            log_admin_action(
                action='LOGIN',
                description=f'Connexion administrateur: {user.get_full_name() or user.username}',
                user=user,
                ip_address=request.META.get('REMOTE_ADDR'),
                details={
                    'user_agent': request.META.get('HTTP_USER_AGENT', ''),
                    'is_superuser': user.is_superuser,
                    'is_staff': user.is_staff,
                }
            )
        except Exception as e:
            # En cas d'erreur, ne pas bloquer la connexion
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Erreur lors de l'enregistrement du log de connexion: {e}")


@receiver(user_login_failed)
def log_failed_login(sender, credentials, request, **kwargs):
    """Enregistre les tentatives de connexion échouées"""
    username = credentials.get('username', 'Unknown')
    
    try:
        log_admin_action(
            action='ERROR',
            description=f'Tentative de connexion échouée pour: {username}',
            user=None,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={
                'username': username,
                'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            }
        )
    except Exception as e:
        # En cas d'erreur, ne pas bloquer la tentative de connexion
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors de l'enregistrement du log de connexion échouée: {e}")
