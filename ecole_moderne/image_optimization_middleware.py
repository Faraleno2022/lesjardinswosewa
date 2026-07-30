"""
Middleware pour servir automatiquement les images optimisées selon le navigateur et la taille d'écran.
"""
import os
import re
from django.conf import settings
from django.http import HttpResponse, Http404
from django.utils.deprecation import MiddlewareMixin
from pathlib import Path

class ImageOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware qui sert automatiquement les images optimisées selon:
    - Le support WebP du navigateur
    - La taille d'écran (responsive)
    - La connexion (détection de connexion lente)
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.static_images_dir = Path(settings.BASE_DIR) / 'static' / 'images'
        self.optimized_dir = self.static_images_dir / 'optimized'
        
        # Patterns d'images à optimiser
        self.image_patterns = [
            r'/static/images/(ecole|carte1|carte2)\.jpg',
        ]
        
        super().__init__(get_response)
    
    def process_request(self, request):
        """Traiter les requêtes d'images pour servir les versions optimisées."""
        
        # Vérifier si c'est une requête d'image
        path = request.path
        if not any(re.match(pattern, path) for pattern in self.image_patterns):
            return None
        
        # Extraire le nom de l'image
        match = re.search(r'/static/images/([^/]+)\.jpg', path)
        if not match:
            return None
        
        image_name = match.group(1)
        
        # Déterminer la meilleure version à servir
        optimized_path = self._get_best_image_version(request, image_name)
        
        if optimized_path and optimized_path.exists():
            return self._serve_optimized_image(optimized_path)
        
        return None
    
    def _get_best_image_version(self, request, image_name):
        """Déterminer la meilleure version d'image à servir."""
        
        # Vérifier le support WebP
        accept_header = request.META.get('HTTP_ACCEPT', '')
        supports_webp = 'image/webp' in accept_header
        
        # Déterminer la taille d'écran à partir du User-Agent ou des headers
        screen_size = self._detect_screen_size(request)
        
        # Priorité: WebP > JPEG optimisé > responsive
        candidates = []
        
        if supports_webp:
            # Version WebP optimisée
            webp_path = self.optimized_dir / f"{image_name}_optimized.webp"
            if webp_path.exists():
                candidates.append(webp_path)
        
        # Version JPEG optimisée
        jpeg_optimized = self.optimized_dir / f"{image_name}_optimized.jpg"
        if jpeg_optimized.exists():
            candidates.append(jpeg_optimized)
        
        # Versions responsive
        if screen_size:
            responsive_path = self.optimized_dir / f"{image_name}_{screen_size}.jpg"
            if responsive_path.exists():
                candidates.append(responsive_path)
        
        # Retourner la première version disponible
        return candidates[0] if candidates else None
    
    def _detect_screen_size(self, request):
        """Détecter la taille d'écran approximative."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        # Détection mobile
        mobile_patterns = [
            'mobile', 'android', 'iphone', 'ipod', 'blackberry', 
            'windows phone', 'opera mini'
        ]
        
        if any(pattern in user_agent for pattern in mobile_patterns):
            return 'sm'  # Small (mobile)
        
        # Détection tablette
        tablet_patterns = ['ipad', 'tablet', 'kindle']
        if any(pattern in user_agent for pattern in tablet_patterns):
            return 'md'  # Medium (tablet)
        
        # Par défaut: desktop
        return 'lg'  # Large (desktop)
    
    def _serve_optimized_image(self, image_path):
        """Servir une image optimisée avec les bons headers."""
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            
            # Déterminer le type MIME
            if image_path.suffix.lower() == '.webp':
                content_type = 'image/webp'
            else:
                content_type = 'image/jpeg'
            
            # Créer la réponse avec les headers optimisés
            response = HttpResponse(image_data, content_type=content_type)
            
            # Headers de cache optimisés
            if settings.DEBUG:
                # En développement: cache court pour voir les changements
                response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
            else:
                # En production: cache long pour les performances
                response['Cache-Control'] = 'public, max-age=31536000'  # 1 an
                response['Expires'] = 'Thu, 31 Dec 2025 23:59:59 GMT'
            
            # Headers d'optimisation
            response['Vary'] = 'Accept, User-Agent'
            response['X-Image-Optimized'] = 'true'
            response['X-Image-Version'] = image_path.name
            
            # Header de taille pour le monitoring
            response['Content-Length'] = str(len(image_data))
            
            return response
            
        except IOError:
            raise Http404("Image optimisée non trouvée")
    
    def process_response(self, request, response):
        """Ajouter des headers d'optimisation aux réponses d'images."""
        
        # Ajouter des hints de préchargement pour les images critiques
        if request.path == '/' or 'home' in request.path:
            # Précharger l'image hero
            preload_header = '</static/images/ecole.jpg>; rel=preload; as=image'
            
            # Ajouter le header Link pour le préchargement
            existing_link = response.get('Link', '')
            if existing_link:
                response['Link'] = f"{existing_link}, {preload_header}"
            else:
                response['Link'] = preload_header
        
        return response
