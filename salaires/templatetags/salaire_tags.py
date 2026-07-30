from django import template
from django.db.models import Count, Q

register = template.Library()

@register.filter
def etats_valides(periode):
    """Retourne le nombre d'états de salaire validés pour une période"""
    return periode.etats_salaire.filter(valide=True).count()

@register.filter
def etats_payes(periode):
    """Retourne le nombre d'états de salaire payés pour une période"""
    return periode.etats_salaire.filter(paye=True).count()

@register.filter
def etats_en_attente(periode):
    """Retourne le nombre d'états de salaire en attente pour une période"""
    return periode.etats_salaire.filter(valide=False, paye=False).count()

@register.simple_tag
def stats_periode(periode):
    """Retourne les statistiques complètes d'une période"""
    etats = periode.etats_salaire.all()
    return {
        'total': etats.count(),
        'valides': etats.filter(valide=True).count(),
        'payes': etats.filter(paye=True).count(),
        'en_attente': etats.filter(valide=False, paye=False).count(),
    }

@register.filter
def get_item(dictionary, key):
    """Récupère un élément d'un dictionnaire par sa clé"""
    if dictionary is None:
        return None
    return dictionary.get(key)

@register.filter
def sum_attr(items, attr):
    """Somme les valeurs d'un attribut dans une liste de dictionnaires"""
    if not items:
        return 0
    total = 0
    for item in items:
        if isinstance(item, dict):
            val = item.get(attr, 0)
        else:
            val = getattr(item, attr, 0)
        if val is not None:
            try:
                total += val
            except (TypeError, ValueError):
                pass
    return total
