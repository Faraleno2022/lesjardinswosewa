from django.apps import AppConfig


class NotesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notes'
    
    def ready(self):
        """Importer les signaux au démarrage de l'application."""
        import notes.signals  # noqa: F401
