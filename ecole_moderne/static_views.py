"""
Vues personnalisées pour la gestion des fichiers statiques avec cache control.
"""
import os
import mimetypes
from django.http import HttpResponse, Http404
from django.conf import settings
from django.utils.http import http_date
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET
import time

@never_cache
@require_GET
def serve_static_no_cache(request, path):
    """
    Sert les fichiers statiques sans cache en développement.
    Utilisé pour forcer le rechargement des images modifiées.
    """
    if not settings.DEBUG:
        raise Http404("Cette vue n'est disponible qu'en mode DEBUG")
    
    # Construire le chemin complet du fichier
    full_path = None
    for static_dir in settings.STATICFILES_DIRS:
        potential_path = os.path.join(static_dir, path)
        if os.path.exists(potential_path) and os.path.isfile(potential_path):
            full_path = potential_path
            break
    
    if not full_path:
        raise Http404(f"Fichier statique non trouvé: {path}")
    
    # Obtenir le type MIME
    content_type, encoding = mimetypes.guess_type(full_path)
    content_type = content_type or 'application/octet-stream'
    
    # Lire le fichier
    try:
        with open(full_path, 'rb') as f:
            content = f.read()
    except IOError:
        raise Http404(f"Impossible de lire le fichier: {path}")
    
    # Créer la réponse avec les en-têtes anti-cache
    response = HttpResponse(content, content_type=content_type)
    
    # En-têtes pour empêcher la mise en cache
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    
    # Ajouter la date de modification comme ETag pour détecter les changements
    try:
        stat = os.stat(full_path)
        response['ETag'] = f'"{int(stat.st_mtime)}"'
        response['Last-Modified'] = http_date(stat.st_mtime)
    except OSError:
        pass
    
    return response

def get_file_version(file_path):
    """
    Obtient la version d'un fichier basée sur sa date de modification.
    """
    try:
        if os.path.exists(file_path):
            return str(int(os.path.getmtime(file_path)))
        else:
            # Si le fichier n'existe pas, retourner un timestamp actuel
            return str(int(time.time()))
    except OSError:
        return str(int(time.time()))
