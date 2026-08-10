from django.apps import AppConfig


class PaiementsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'paiements'

    def ready(self):
        # Importe les signaux une seule fois au démarrage de Django.
        from . import signals  # noqa: F401
