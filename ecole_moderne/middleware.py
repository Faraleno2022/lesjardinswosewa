"""
Middleware d'optimisation des performances pour l'application
"""
from django.core.cache import cache
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse
import time
import logging

logger = logging.getLogger(__name__)

class PerformanceMiddleware(MiddlewareMixin):
    """
    Middleware pour optimiser les performances globales
    """
    
    def process_request(self, request):
        """Traitement avant la vue"""
        request.start_time = time.time()
        
        # Cache des données utilisateur fréquemment utilisées
        if request.user.is_authenticated:
            self._cache_user_data(request)
    
    def process_response(self, request, response):
        """Traitement après la vue"""
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Log des vues lentes
            if duration > 2.0:  # Plus de 2 secondes
                logger.warning(
                    f"Vue lente: {request.path} - {duration:.2f}s - User: {request.user.id if request.user.is_authenticated else 'Anonymous'}"
                )
            
            # Ajouter header de performance
            response['X-Response-Time'] = f"{duration:.3f}s"
        
        return response
    
    def _cache_user_data(self, request):
        """Met en cache les données utilisateur fréquemment utilisées"""
        user_id = request.user.id
        
        # Cache de l'école utilisateur
        cache_key = f'user_school_{user_id}'
        if not cache.get(cache_key):
            try:
                from utilisateurs.utils import user_school
                school = user_school(request.user)
                if school:
                    cache.set(cache_key, school, 300)  # 5 minutes
            except:
                pass
        
        # Cache des permissions utilisateur
        perms_cache_key = f'user_perms_{user_id}'
        if not cache.get(perms_cache_key):
            try:
                from utilisateurs.utils import user_is_admin
                perms = {
                    'is_admin': user_is_admin(request.user),
                    'is_superuser': request.user.is_superuser,
                    'is_staff': request.user.is_staff,
                }
                cache.set(perms_cache_key, perms, 600)  # 10 minutes
            except:
                pass

class CacheControlMiddleware(MiddlewareMixin):
    """
    Middleware pour contrôler le cache des réponses
    """
    
    def process_response(self, request, response):
        """Ajoute des headers de cache appropriés"""
        
        # Pages statiques - cache long
        if request.path.startswith('/static/') or request.path.startswith('/media/'):
            response['Cache-Control'] = 'public, max-age=31536000'  # 1 an
            return response
        
        # API et AJAX - pas de cache
        if request.path.startswith('/api/') or request.is_ajax():
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            return response
        
        # Pages de formulaires - pas de cache
        if request.method == 'POST' or 'form' in request.path:
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            return response
        
        # Pages de consultation - cache court
        if request.method == 'GET':
            response['Cache-Control'] = 'public, max-age=300'  # 5 minutes
        
        return response

class DatabaseOptimizationMiddleware(MiddlewareMixin):
    """
    Middleware pour optimiser les requêtes de base de données
    """
    
    def process_request(self, request):
        """Initialise le compteur de requêtes"""
        from django.db import connection
        request.queries_start = len(connection.queries)
    
    def process_response(self, request, response):
        """Log le nombre de requêtes exécutées"""
        if hasattr(request, 'queries_start'):
            from django.db import connection
            queries_count = len(connection.queries) - request.queries_start
            
            # Log si trop de requêtes
            if queries_count > 20:
                logger.warning(
                    f"Trop de requêtes DB: {request.path} - {queries_count} requêtes - User: {request.user.id if request.user.is_authenticated else 'Anonymous'}"
                )
            
            # Ajouter header du nombre de requêtes
            response['X-DB-Queries'] = str(queries_count)
        
        return response
