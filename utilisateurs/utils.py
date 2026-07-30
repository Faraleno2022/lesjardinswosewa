from typing import Any
from django.contrib.auth.models import User
from django.db.models import QuerySet


def user_is_superadmin(user: User) -> bool:
    """Vérifie si l'utilisateur est un super-administrateur (peut voir toutes les écoles)"""
    return getattr(user, 'is_superuser', False)


def user_is_admin(user: User) -> bool:
    """Vérifie si l'utilisateur a des droits d'administration (pour son école)
    Note: Cela inclut les superusers ET les admins d'école, mais ne signifie pas
    qu'ils peuvent voir toutes les écoles. Utilisez user_is_superadmin pour cela.
    """
    try:
        return user.is_superuser or (hasattr(user, 'profil') and user.profil.role == 'ADMIN')
    except Exception:
        return user.is_superuser


def user_school(user: User):
    """Retourne l'école de l'utilisateur"""
    if hasattr(user, 'profil'):
        return user.profil.ecole
    return None


def filter_by_user_school(qs: QuerySet, user: User, field_path: str = 'ecole') -> QuerySet:
    """Filter a queryset by the user's school unless the user is superadmin.
    field_path can be like 'classe__ecole' or 'enseignant__ecole'.
    
    IMPORTANT: Seul le superuser peut voir toutes les écoles.
    Les utilisateurs avec rôle ADMIN sont filtrés par leur école.
    """
    # Seul le superutilisateur voit toutes les écoles
    if user_is_superadmin(user):
        return qs
    ecole = user_school(user)
    if ecole is None:
        # If no school is set, return empty queryset to avoid data leakage
        return qs.none()
    return qs.filter(**{field_path: ecole})
