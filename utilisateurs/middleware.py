"""
Middleware pour l'isolation des données par école
"""
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib import messages
from django.urls import reverse
import logging

logger = logging.getLogger(__name__)

class EcoleIsolationMiddleware:
    """
    Middleware qui assure l'isolation des données par école.
    Empêche les utilisateurs de voir les données d'autres écoles.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Code à exécuter pour chaque requête avant la vue
        response = self.get_response(request)
        # Code à exécuter pour chaque requête/réponse après la vue
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        """
        Vérifie l'accès aux données selon l'école de l'utilisateur.
        """
        # Ignorer pour les superusers et les utilisateurs non connectés
        if not request.user.is_authenticated or request.user.is_superuser:
            return None
            
        # Ignorer pour certaines vues système
        if self._is_system_view(request):
            return None
            
        # Vérifier le profil utilisateur
        profil = getattr(request.user, 'profil', None)
        if not profil:
            logger.warning(f"Utilisateur {request.user.username} sans profil tente d'accéder à {request.path}")
            messages.error(request, "Votre profil n'est pas configuré. Contactez l'administrateur FARA LENO AU +224622613559.")
            return redirect('home')
            
        # Vérifier si le profil est validé
        if not profil.is_validated:
            logger.warning(f"Utilisateur {request.user.username} non validé tente d'accéder à {request.path}")
            messages.error(request, "Votre compte n'est pas encore validé par l'administrateur.")
            return redirect('home')
            
        # Vérifier si l'utilisateur a une école assignée
        if not profil.ecole:
            logger.warning(f"Utilisateur {request.user.username} sans école tente d'accéder à {request.path}")
            messages.error(request, "Aucune école assignée à votre compte. Contactez l'administrateur FARA LENO AU +224622613559.")
            return redirect('home')
            
        # Stocker l'école de l'utilisateur dans la requête pour un accès facile
        request.user_ecole = profil.ecole
        
        return None
    
    def _is_system_view(self, request):
        """
        Détermine si la vue est une vue système qui ne nécessite pas de vérification d'école.
        """
        from django.conf import settings
        system_paths = [
            '/' + getattr(settings, 'ADMIN_URL', 'admin/'),
            '/utilisateurs/login/',
            '/utilisateurs/logout/',
            '/utilisateurs/password/',
            '/static/',
            '/media/',
            '/favicon.ico',
            '/',  # Page d'accueil
        ]
        
        # Vues d'administration des utilisateurs (pour les admins)
        admin_paths = [
            '/utilisateurs/comptes-en-attente/',
            '/utilisateurs/valider-compte/',
            '/utilisateurs/security/',
        ]
        
        path = request.path
        
        # Vérifier les chemins système
        for system_path in system_paths:
            if path.startswith(system_path):
                return True
                
        # Vérifier les chemins admin (seulement pour les admins)
        for admin_path in admin_paths:
            if path.startswith(admin_path):
                profil = getattr(request.user, 'profil', None)
                return profil and profil.role == 'ADMIN'
                
        return False


def filter_by_user_school(queryset, user, school_field='ecole'):
    """
    Fonction utilitaire pour filtrer un queryset par l'école de l'utilisateur.
    
    Args:
        queryset: QuerySet à filtrer
        user: Utilisateur connecté
        school_field: Nom du champ qui référence l'école (par défaut 'ecole')
    
    Returns:
        QuerySet filtré par l'école de l'utilisateur
    """
    # Les superusers voient tout
    if user.is_superuser:
        return queryset
        
    # Vérifier le profil utilisateur
    profil = getattr(user, 'profil', None)
    if not profil or not profil.ecole:
        # Aucune école = aucun résultat
        return queryset.none()
        
    # Filtrer par l'école de l'utilisateur
    filter_kwargs = {school_field: profil.ecole}
    return queryset.filter(**filter_kwargs)


def check_school_access(user, obj, school_field='ecole'):
    """
    Vérifie si un utilisateur a accès à un objet selon son école.
    
    Args:
        user: Utilisateur connecté
        obj: Objet à vérifier
        school_field: Nom du champ qui référence l'école
    
    Returns:
        bool: True si l'utilisateur a accès, False sinon
    """
    # Les superusers ont accès à tout
    if user.is_superuser:
        return True
        
    # Vérifier le profil utilisateur
    profil = getattr(user, 'profil', None)
    if not profil or not profil.ecole:
        return False
        
    # Récupérer l'école de l'objet
    obj_school = obj
    for field in school_field.split('__'):
        if hasattr(obj_school, field):
            obj_school = getattr(obj_school, field)
        else:
            return False
            
    # Comparer les écoles
    return obj_school == profil.ecole


class SchoolAccessMixin:
    """
    Mixin pour les vues basées sur les classes qui assure l'isolation par école.
    """
    school_field = 'ecole'  # Champ qui référence l'école
    
    def get_queryset(self):
        """Filtre le queryset par l'école de l'utilisateur."""
        queryset = super().get_queryset()
        return filter_by_user_school(queryset, self.request.user, self.school_field)
    
    def get_object(self, queryset=None):
        """Vérifie l'accès à l'objet selon l'école."""
        obj = super().get_object(queryset)
        if not check_school_access(self.request.user, obj, self.school_field):
            raise Http404("Objet non trouvé ou accès non autorisé.")
        return obj


class LectureSeuleMiddleware:
    """Bloque toute action (POST/PUT/PATCH/DELETE) pour les utilisateurs en
    mode lecture seule, dans TOUS les modules. La consultation (GET) reste
    autorisée. Les superutilisateurs ne sont jamais bloqués.
    """
    METHODES_SURES = ('GET', 'HEAD', 'OPTIONS', 'TRACE')
    # Chemins autorisés même en écriture (déconnexion notamment)
    CHEMINS_AUTORISES = (
        '/utilisateurs/logout/',
        '/utilisateurs/deconnexion/',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (user is not None and user.is_authenticated and not user.is_superuser
                and request.method not in self.METHODES_SURES):
            profil = getattr(user, 'profil', None)
            if profil is not None and getattr(profil, 'lecture_seule', False):
                path = request.path or ''
                if not any(path.startswith(p) for p in self.CHEMINS_AUTORISES):
                    # Requête AJAX : renvoyer un 403 JSON
                    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                        from django.http import JsonResponse
                        return JsonResponse(
                            {'success': False,
                             'error': "Accès en lecture seule : action non autorisée."},
                            status=403)
                    messages.error(
                        request,
                        "🔒 Votre compte est en lecture seule : vous pouvez consulter mais pas effectuer cette action.")
                    retour = request.META.get('HTTP_REFERER') or '/'
                    return redirect(retour)
        return self.get_response(request)
