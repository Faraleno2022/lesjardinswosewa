"""
Utilitaire pour la gestion de l'année scolaire active.
Centralise la logique de récupération de l'année active depuis la session.
"""
from datetime import date, timedelta

from django.conf import settings

from .models import Classe

SESSION_ANNEE_ACTIVE = 'annee_scolaire_active'


def get_annee_active(request, ecole):
    """Retourne l'année scolaire active (session ou la plus récente).

    L'année est déterminée par :
    1. La valeur stockée en session (si elle correspond à une année existante)
    2. L'année la plus récente pour l'école donnée
    """
    if not ecole:
        return None
    annees = list(
        Classe.objects
        .filter(ecole=ecole)
        .values_list('annee_scolaire', flat=True)
        .distinct()
        .order_by('-annee_scolaire')
    )
    if not annees:
        return None
    annee_session = request.session.get(SESSION_ANNEE_ACTIVE)
    if annee_session and annee_session in annees:
        return annee_session
    return annees[0]


def get_debut_periode_reporting(request, ecole=None, today=None):
    """Début par défaut des rapports financiers.

    La période couvre au minimum les douze derniers mois. Elle remonte aussi
    au début (1er août) de l'année scolaire active lorsque celui-ci est plus
    ancien. Ainsi, un changement de mois ou la préparation anticipée d'une
    nouvelle année scolaire ne masque pas les encaissements récents.
    """
    today = today or date.today()
    debut_glissant = today - timedelta(days=365)
    annee = get_annee_active(request, ecole) if ecole else None
    if not annee:
        return debut_glissant

    try:
        debut_annee = date(int(str(annee).split('-')[0]), 8, 1)
    except (TypeError, ValueError, IndexError):
        return debut_glissant
    return min(debut_annee, debut_glissant)


def annee_suivante(annee: str) -> str:
    """Calcule l'annee scolaire suivante. Ex: 2025-2026 -> 2026-2027."""
    try:
        debut, fin = str(annee).split('-')
        return f"{int(debut) + 1}-{int(fin) + 1}"
    except Exception:
        return annee


def date_fin_annee_scolaire(annee: str):
    """Retourne la date de fin configuree pour une annee scolaire."""
    try:
        _, fin = str(annee).split('-')
        fin_annee = int(fin)
        fin_mois = int(getattr(settings, 'ANNEE_SCOLAIRE_FIN_MOIS', 6))
        fin_jour = int(getattr(settings, 'ANNEE_SCOLAIRE_FIN_JOUR', 30))
        return date(fin_annee, fin_mois, fin_jour)
    except Exception:
        return None


def get_statut_creation_nouvelle_annee(ecole, today=None):
    """Indique si la nouvelle annee doit etre preparee pour l'ecole."""
    if not ecole:
        return {'due': False}

    annee_courante = (
        Classe.objects
        .filter(ecole=ecole)
        .values_list('annee_scolaire', flat=True)
        .distinct()
        .order_by('-annee_scolaire')
        .first()
    )
    if not annee_courante:
        return {'due': False}

    fin = date_fin_annee_scolaire(annee_courante)
    if not fin:
        return {'due': False}

    today = today or date.today()
    prochaine = annee_suivante(annee_courante)
    prochaine_existe = Classe.objects.filter(
        ecole=ecole,
        annee_scolaire=prochaine,
    ).exists()

    return {
        'due': today > fin and not prochaine_existe,
        'annee_courante': annee_courante,
        'annee_nouvelle': prochaine,
        'date_fin': fin,
        'nouvelle_existe': prochaine_existe,
    }
