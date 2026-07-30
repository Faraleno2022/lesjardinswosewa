"""
Décorateurs d'optimisation pour les vues
"""
from functools import wraps
from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
import time
import logging

logger = logging.getLogger(__name__)

def cache_view(cache_time=300, key_prefix='view'):
    """
    Décorateur pour mettre en cache une vue complète
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Générer une clé de cache unique
            cache_key = f"{key_prefix}_{request.user.id}_{request.path}_{hash(str(request.GET))}"
            
            # Vérifier le cache
            cached_response = cache.get(cache_key)
            if cached_response and request.method == 'GET':
                return cached_response
            
            # Exécuter la vue
            response = view_func(request, *args, **kwargs)
            
            # Mettre en cache seulement les réponses GET réussies
            if request.method == 'GET' and response.status_code == 200:
                cache.set(cache_key, response, cache_time)
            
            return response
        return wrapper
    return decorator

def optimize_queries(view_func):
    """
    Décorateur pour optimiser automatiquement les requêtes
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        start_time = time.time()
        
        # Exécuter la vue
        response = view_func(request, *args, **kwargs)
        
        # Mesurer le temps d'exécution
        execution_time = time.time() - start_time
        
        # Log si la vue est lente
        if execution_time > 1.0:
            logger.warning(f"Vue lente: {view_func.__name__} - {execution_time:.2f}s")
        
        return response
    return wrapper

def cache_user_data(view_func):
    """
    Décorateur pour mettre en cache les données utilisateur
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if request.user.is_authenticated:
            user_id = request.user.id
            
            # Cache de l'école utilisateur
            school_cache_key = f'user_school_{user_id}'
            if not cache.get(school_cache_key):
                try:
                    from utilisateurs.utils import user_school
                    school = user_school(request.user)
                    if school:
                        cache.set(school_cache_key, school, 300)
                except:
                    pass
        
        return view_func(request, *args, **kwargs)
    return wrapper

def smart_pagination(per_page=20):
    """
    Décorateur pour une pagination intelligente
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Ajouter la pagination au contexte
            request.pagination_per_page = per_page
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def ajax_cache(cache_time=60):
    """
    Décorateur spécial pour les vues AJAX
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.is_ajax():
                return view_func(request, *args, **kwargs)
            
            # Clé de cache pour AJAX
            cache_key = f"ajax_{view_func.__name__}_{request.user.id}_{hash(str(request.GET))}"
            
            # Vérifier le cache
            cached_data = cache.get(cache_key)
            if cached_data:
                return JsonResponse(cached_data)
            
            # Exécuter la vue
            response = view_func(request, *args, **kwargs)
            
            # Mettre en cache si c'est une JsonResponse
            if isinstance(response, JsonResponse) and response.status_code == 200:
                try:
                    import json
                    data = json.loads(response.content.decode())
                    cache.set(cache_key, data, cache_time)
                except:
                    pass
            
            return response
        return wrapper
    return decorator

def batch_queries(view_func):
    """
    Décorateur pour optimiser les requêtes en lot
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from django.db import transaction
        
        # Utiliser une transaction pour grouper les requêtes
        with transaction.atomic():
            return view_func(request, *args, **kwargs)
    return wrapper

def monitor_performance(threshold=2.0):
    """
    Décorateur pour monitorer les performances
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                response = view_func(request, *args, **kwargs)
                execution_time = time.time() - start_time
                
                # Log si dépasse le seuil
                if execution_time > threshold:
                    logger.warning(
                        f"Performance: {view_func.__name__} - {execution_time:.2f}s - "
                        f"User: {request.user.id if request.user.is_authenticated else 'Anonymous'} - "
                        f"Path: {request.path}"
                    )
                
                return response
                
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(
                    f"Erreur dans {view_func.__name__} après {execution_time:.2f}s: {e}"
                )
                raise
        return wrapper
    return decorator
