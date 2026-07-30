from django.apps import AppConfig


class ElevesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'eleves'
    
    def ready(self):
        """Importer les signals lors du démarrage de l'application"""
        import eleves.signals
