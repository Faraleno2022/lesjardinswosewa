import os
from django.conf import settings
from .models import Profil
from .permissions import get_user_permissions, check_comptable_restrictions
from ecole_moderne.branding import get_school_branding

def user_context(request):
    """
    Ajoute des informations utilisateur au contexte global
    """
    context = {
        'user_profil': None,
        'user_role': None,
        'user_ecole': None,
        'is_admin': False,
        'user_permissions': {},
        'user_restrictions': {},
        'annee_active': None,
        'nouvelle_annee_status': {'due': False},
        # Mode hors-ligne : True quand lancé depuis l'exe PyInstaller
        'is_offline': os.environ.get('OFFLINE_MODE', '0') == '1',
        'session_idle_timeout_seconds': getattr(
            settings,
            'SESSION_IDLE_TIMEOUT_SECONDS',
            1800,
        ),
        'school_branding': get_school_branding(),
    }

    if request.user.is_authenticated:
        try:
            profil = request.user.profil
            context.update({
                'user_profil': profil,
                'user_role': profil.role,
                'user_ecole': profil.ecole,
                'is_admin': request.user.is_superuser or profil.role == 'ADMIN',
                'user_permissions': get_user_permissions(request.user),
                'user_restrictions': check_comptable_restrictions(request.user),
            })
            # Ajouter l'année scolaire active au contexte global
            if profil.ecole:
                from eleves.utils_annee import (
                    get_annee_active,
                    get_statut_creation_nouvelle_annee,
                )
                context['annee_active'] = get_annee_active(request, profil.ecole)
                context['nouvelle_annee_status'] = get_statut_creation_nouvelle_annee(profil.ecole)
                context['school_branding'] = get_school_branding(profil.ecole)
        except Profil.DoesNotExist:
            context.update({
                'user_permissions': get_user_permissions(request.user),
                'user_restrictions': check_comptable_restrictions(request.user),
            })

    return context
