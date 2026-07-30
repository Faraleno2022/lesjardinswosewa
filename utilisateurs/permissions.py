"""
Décorateurs et fonctions pour gérer les permissions granulaires des utilisateurs
"""
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)

def has_permission(user, permission_name):
    """
    Vérifie si un utilisateur a une permission spécifique
    """
    if not user.is_authenticated:
        return False
    
    # Les superusers ont toutes les permissions
    if user.is_superuser:
        return True
    
    # Vérifier le profil utilisateur
    profil = getattr(user, 'profil', None)
    if not profil:
        return False
    
    # Les admins ont toutes les permissions
    if profil.role == 'ADMIN':
        return True

    # Règles métier implicites par rôle
    # Autoriser les COMPTABLES à valider les paiements/échéances et gérer les notes sans avoir à cocher manuellement
    if profil.role == 'COMPTABLE' and permission_name in {'peut_valider_paiements', 'peut_gerer_notes', 'peut_importer_eleves'}:
        return True
    
    # Vérifier la permission spécifique
    return getattr(profil, permission_name, False)

def has_any_permission(user, permission_names):
    """
    Vérifie si l'utilisateur possède AU MOINS une des permissions listées
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profil = getattr(user, 'profil', None)
    if not profil:
        return False
    if getattr(profil, 'role', None) == 'ADMIN':
        return True
    for perm in permission_names:
        if getattr(profil, perm, False):
            return True
    return False

def permission_required(permission_name, message=None):
    """
    Décorateur pour vérifier qu'un utilisateur a une permission spécifique
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_permission(request.user, permission_name):
                # Log de la tentative d'accès non autorisée
                logger.warning(
                    f"Accès refusé: {request.user.username} a tenté d'accéder à {view_func.__name__} "
                    f"sans la permission {permission_name}"
                )
                
                # Message personnalisé ou par défaut
                error_message = message or f"Vous n'avez pas la permission requise: {permission_name}"
                
                return render(request, 'utilisateurs/permission_denied.html', {
                    'error_message': error_message,
                    'permission_name': permission_name,
                    'user_role': getattr(request.user.profil, 'role', 'INCONNU') if hasattr(request.user, 'profil') else 'INCONNU'
                }, status=403)
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def any_permission_required(permission_names, message=None):
    """
    Décorateur: autorise l'accès si l'utilisateur a AU MOINS UNE des permissions.
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not has_any_permission(request.user, permission_names):
                logger.warning(
                    f"Accès refusé: {request.user.username} a tenté d'accéder à {view_func.__name__} "
                    f"sans les permissions requises (any of): {permission_names}"
                )
                error_message = message or "Vous n'avez pas les permissions requises."
                return render(request, 'utilisateurs/permission_denied.html', {
                    'error_message': error_message,
                    'permission_name': ','.join(permission_names),
                    'user_role': getattr(request.user.profil, 'role', 'INCONNU') if hasattr(request.user, 'profil') else 'INCONNU'
                }, status=403)
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def can_add_payments(view_func):
    """Décorateur pour vérifier la permission d'ajouter des paiements"""
    return permission_required(
        'peut_ajouter_paiements',
        "Vous n'êtes pas autorisé à ajouter des paiements."
    )(view_func)

def can_apply_discounts(view_func):
    """
    Autorise l'accès aux écrans d'application/édition des remises si l'utilisateur
    possède au moins une des permissions suivantes:
    - peut_valider_paiements
    - peut_modifier_paiements
    Cela couvre notamment le rôle COMPTABLE quand configuré.
    """
    return any_permission_required(
        ['peut_valider_paiements', 'peut_modifier_paiements'],
        "Vous n'êtes pas autorisé à appliquer des remises."
    )(view_func)

def can_add_expenses(view_func):
    """Décorateur pour vérifier la permission d'ajouter des dépenses"""
    return permission_required(
        'peut_ajouter_depenses',
        "Vous n'êtes pas autorisé à ajouter des dépenses."
    )(view_func)

def can_add_teachers(view_func):
    """Décorateur pour vérifier la permission d'ajouter des enseignants"""
    return permission_required(
        'peut_ajouter_enseignants',
        "Vous n'êtes pas autorisé à ajouter des enseignants."
    )(view_func)

def can_modify_payments(view_func):
    """Décorateur pour vérifier la permission de modifier des paiements"""
    return permission_required(
        'peut_modifier_paiements',
        "Vous n'êtes pas autorisé à modifier des paiements."
    )(view_func)

def can_modify_expenses(view_func):
    """Décorateur pour vérifier la permission de modifier des dépenses"""
    return permission_required(
        'peut_modifier_depenses',
        "Vous n'êtes pas autorisé à modifier des dépenses."
    )(view_func)

def can_delete_payments(view_func):
    """Décorateur pour vérifier la permission de supprimer des paiements"""
    return permission_required(
        'peut_supprimer_paiements',
        "Vous n'êtes pas autorisé à supprimer des paiements."
    )(view_func)

def can_delete_expenses(view_func):
    """Décorateur pour vérifier la permission de supprimer des dépenses"""
    return permission_required(
        'peut_supprimer_depenses',
        "Vous n'êtes pas autorisé à supprimer des dépenses."
    )(view_func)

def can_delete_subscriptions(view_func):
    """Décorateur pour vérifier la permission de supprimer des abonnements"""
    return permission_required(
        'peut_supprimer_abonnements',
        "Vous n'êtes pas autorisé à supprimer des abonnements."
    )(view_func)

def can_validate_payments(view_func):
    """Décorateur pour vérifier la permission de valider des paiements"""
    return permission_required(
        'peut_valider_paiements',
        "Vous n'êtes pas autorisé à valider des paiements."
    )(view_func)

def can_validate_expenses(view_func):
    """Décorateur pour vérifier la permission de valider des dépenses"""
    return permission_required(
        'peut_valider_depenses',
        "Vous n'êtes pas autorisé à valider des dépenses."
    )(view_func)

def can_generate_reports(view_func):
    """Décorateur pour vérifier la permission de générer des rapports"""
    return permission_required(
        'peut_generer_rapports',
        "Vous n'êtes pas autorisé à générer des rapports."
    )(view_func)

def can_view_reports(view_func):
    """Décorateur pour vérifier la permission de consulter des rapports"""
    return permission_required(
        'peut_consulter_rapports',
        "Vous n'êtes pas autorisé à consulter des rapports."
    )(view_func)

def can_manage_notes(view_func):
    """Décorateur pour vérifier la permission de gérer les notes et matières"""
    return permission_required(
        'peut_gerer_notes',
        "Vous n'êtes pas autorisé à gérer les notes et matières."
    )(view_func)

def can_manage_users(view_func):
    """Décorateur pour vérifier la permission de gérer des utilisateurs"""
    return permission_required(
        'peut_gerer_utilisateurs',
        "Vous n'êtes pas autorisé à gérer des utilisateurs."
    )(view_func)

# Fonctions utilitaires pour les templates
def get_user_permissions(user):
    """
    Retourne un dictionnaire des permissions de l'utilisateur
    """
    if not user.is_authenticated:
        return {}
    
    if user.is_superuser:
        return {
            'can_add_payments': True,
            'can_add_expenses': True,
            'can_add_teachers': True,
            'can_modify_payments': True,
            'can_modify_expenses': True,
            'can_delete_payments': True,
            'can_delete_expenses': True,
            'can_delete_subscriptions': True,
            'can_validate_payments': True,
            'can_validate_expenses': True,
            'can_generate_reports': True,
            'can_view_reports': True,
            'can_manage_users': True,
            'can_manage_notes': True,
        }
    
    profil = getattr(user, 'profil', None)
    if not profil:
        return {}
    
    if profil.role == 'ADMIN':
        return {
            'can_add_payments': True,
            'can_add_expenses': True,
            'can_add_teachers': True,
            'can_modify_payments': True,
            'can_modify_expenses': True,
            'can_delete_payments': True,
            'can_delete_expenses': True,
            'can_delete_subscriptions': True,
            'can_validate_payments': True,
            'can_validate_expenses': True,
            'can_generate_reports': True,
            'can_view_reports': True,
            'can_manage_users': True,
            'can_manage_notes': True,
        }
    
    # Par défaut, calcul pour les autres rôles
    can_validate_paiements = profil.peut_valider_paiements or (profil.role == 'COMPTABLE')
    can_manage_notes = profil.peut_gerer_notes or (profil.role == 'COMPTABLE')
    return {
        'can_add_payments': profil.peut_ajouter_paiements,
        'can_add_expenses': profil.peut_ajouter_depenses,
        'can_add_teachers': profil.peut_ajouter_enseignants,
        'can_modify_payments': profil.peut_modifier_paiements,
        'can_modify_expenses': profil.peut_modifier_depenses,
        'can_delete_payments': profil.peut_supprimer_paiements,
        'can_delete_expenses': profil.peut_supprimer_depenses,
        'can_delete_subscriptions': profil.peut_supprimer_abonnements,
        'can_validate_payments': can_validate_paiements,
        'can_validate_expenses': profil.peut_valider_depenses,
        'can_generate_reports': profil.peut_generer_rapports,
        'can_view_reports': profil.peut_consulter_rapports,
        'can_manage_users': profil.peut_gerer_utilisateurs,
        'can_manage_notes': can_manage_notes,
    }

def check_comptable_restrictions(user):
    """
    Vérifie les restrictions spécifiques pour les comptables
    Retourne un dictionnaire des restrictions
    """
    if not user.is_authenticated:
        return {'all_restricted': True}
    
    if user.is_superuser:
        return {'all_restricted': False}
    
    profil = getattr(user, 'profil', None)
    if not profil:
        return {'all_restricted': True}
    
    if profil.role in ['ADMIN', 'DIRECTEUR']:
        return {'all_restricted': False}
    
    if profil.role == 'COMPTABLE':
        return {
            'all_restricted': False,
            'cannot_add_payments': not profil.peut_ajouter_paiements,
            'cannot_add_expenses': not profil.peut_ajouter_depenses,
            'cannot_add_teachers': not profil.peut_ajouter_enseignants,
            'cannot_modify_payments': not profil.peut_modifier_paiements,
            'cannot_modify_expenses': not profil.peut_modifier_depenses,
            'cannot_delete_payments': not profil.peut_supprimer_paiements,
            'cannot_delete_expenses': not profil.peut_supprimer_depenses,
            'cannot_delete_subscriptions': not profil.peut_supprimer_abonnements,
        }
    
    return {'all_restricted': True}
