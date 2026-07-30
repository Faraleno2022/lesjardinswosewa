"""
Middleware pour gérer le cache des images en développement.
"""
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

class ImageCacheMiddleware(MiddlewareMixin):
    """
    Middleware qui ajoute des en-têtes anti-cache aux images en développement
    pour forcer leur rechargement automatique.
    """
    
    def process_response(self, request, response):
        # Seulement en mode DEBUG
        if not settings.DEBUG:
            return response
        
        # Vérifier si c'est une requête pour une image
        path = request.path
        if (path.startswith('/static/images/') and 
            any(path.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'])):
            
            # Ajouter les en-têtes anti-cache
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
            # Ajouter un en-tête personnalisé pour identifier les images sans cache
            response['X-Image-Cache'] = 'disabled'
        
        return response
