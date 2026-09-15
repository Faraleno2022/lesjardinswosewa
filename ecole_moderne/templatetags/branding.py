"""Acces securise a la charte graphique depuis les gabarits HTML/PDF."""

from django import template

from ecole_moderne.branding import get_document_branding


register = template.Library()


@register.simple_tag
def school_document_branding(ecole=None, bulletin=False):
    """Retourne la palette d'une ecole, avec le theme bulletin si demande."""
    return get_document_branding(ecole, bulletin=bool(bulletin))
