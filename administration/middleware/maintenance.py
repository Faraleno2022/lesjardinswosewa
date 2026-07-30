from django.http import HttpResponse
from django.template import Template, Context
from django.utils.deprecation import MiddlewareMixin
from django.urls import reverse
from administration.models import MaintenanceMode


class MaintenanceMiddleware(MiddlewareMixin):
    """Middleware pour gérer le mode maintenance"""
    
    def process_request(self, request):
        # Vérifier si le mode maintenance est actif
        try:
            maintenance = MaintenanceMode.objects.first()
            if not maintenance or not maintenance.is_active:
                return None
        except:
            # Si erreur DB, ne pas bloquer
            return None
        
        # Chemins toujours autorisés
        from django.conf import settings
        allowed_paths = [
            '/' + getattr(settings, 'ADMIN_URL', 'admin/'),
            '/static/',
            '/media/',
            reverse('administration:dashboard'),
            reverse('administration:toggle_maintenance'),
        ]
        
        # Vérifier si le chemin est autorisé
        for path in allowed_paths:
            if request.path.startswith(path):
                return None
        
        # Vérifier si l'utilisateur est autorisé
        if request.user.is_authenticated:
            if (request.user.is_superuser or 
                request.user.is_staff or 
                maintenance.allowed_users.filter(id=request.user.id).exists()):
                return None
        
        # Afficher la page de maintenance
        template = Template("""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Maintenance en cours</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
            <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
            <style>
                body {
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    min-height: 100vh;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .maintenance-card {
                    background: white;
                    border-radius: 15px;
                    box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                    padding: 3rem;
                    text-align: center;
                    max-width: 500px;
                }
                .maintenance-icon {
                    font-size: 4rem;
                    color: #ffc107;
                    margin-bottom: 1rem;
                }
            </style>
        </head>
        <body>
            <div class="maintenance-card">
                <i class="fas fa-tools maintenance-icon"></i>
                <h1 class="mb-3">Maintenance en cours</h1>
                <p class="lead mb-4">{{ message }}</p>
                <p class="text-muted">
                    <i class="fas fa-clock"></i>
                    Nous travaillons pour améliorer votre expérience.
                </p>
                <hr>
                <small class="text-muted">
                    Si vous êtes administrateur,
                    <a href="/utilisateurs/login/" class="text-decoration-none">connectez-vous ici</a>
                </small>
            </div>
        </body>
        </html>
        """)
        
        context = Context({'message': maintenance.message})
        return HttpResponse(template.render(context), status=503)
