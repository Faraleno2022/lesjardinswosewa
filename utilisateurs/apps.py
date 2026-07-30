from django.apps import AppConfig


class UtilisateursConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'utilisateurs'

    def ready(self):
        # Importer les signaux pour créer automatiquement les profils
        try:
            from . import signals  # noqa: F401
        except Exception:
            # Ne pas bloquer le démarrage si une erreur survient
            pass
