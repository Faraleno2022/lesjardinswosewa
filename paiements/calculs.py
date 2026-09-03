"""Règles comptables communes au moteur de paiement.

Ce module ne dépend d'aucun modèle applicatif afin de pouvoir être utilisé
partout (modèles, vues, exports, rapports et commandes) sans import circulaire.
"""

import unicodedata

from django.db.models import Q


CATEGORIE_AUTO = "AUTO"
CATEGORIE_SCOLARITE = "SCOLARITE"
CATEGORIE_CANTINE = "CANTINE"
CATEGORIE_TRANSPORT = "TRANSPORT"
CATEGORIE_FOURNITURES = "FOURNITURES"
CATEGORIE_UNIFORME = "UNIFORME"
CATEGORIE_ACTIVITES = "ACTIVITES"
CATEGORIE_AUTRE = "AUTRE"


def normaliser_libelle(value):
    """Normalise un libellé (minuscules, sans accents, espaces propres)."""
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(without_accents.split())


def categorie_depuis_libelle(value):
    """Déduit la catégorie d'un ancien type de paiement depuis son libellé."""
    label = normaliser_libelle(value)
    compact = "".join(char for char in label if char.isalnum())

    if any(word in compact for word in ("cantine", "restauration")):
        return CATEGORIE_CANTINE
    if any(word in compact for word in ("transport", "bus")):
        return CATEGORIE_TRANSPORT
    if any(word in compact for word in ("fourniture", "livre", "cahier")):
        return CATEGORIE_FOURNITURES
    if any(word in compact for word in ("uniforme", "tenue")):
        return CATEGORIE_UNIFORME
    if any(word in compact for word in ("activite", "sortie", "excursion")):
        return CATEGORIE_ACTIVITES
    if any(
        word in compact
        # « scolar » et non « scolarite » : même radical que le filtre SQL, afin
        # que la détection Python et la requête ne divergent jamais.
        for word in (
            "scolar",
            "inscription",
            "reinscription",
            "tranche",
            "annuel",
        )
    ):
        return CATEGORIE_SCOLARITE
    return CATEGORIE_AUTRE


def categorie_effective(type_paiement):
    """Retourne la catégorie explicite ou la compatibilité par ancien libellé."""
    categorie = getattr(type_paiement, "categorie", CATEGORIE_AUTO) or CATEGORIE_AUTO
    if categorie == CATEGORIE_AUTO:
        return categorie_depuis_libelle(getattr(type_paiement, "nom", type_paiement))
    return categorie


def est_type_scolarite(type_paiement):
    return categorie_effective(type_paiement) == CATEGORIE_SCOLARITE


def filtre_types_scolarite(prefix="type_paiement"):
    """Q réutilisable pour ne sélectionner que les encaissements de scolarité.

    ``AUTO`` maintient la compatibilité avec les types créés avant la migration
    ou par des intégrations qui n'envoient pas encore la catégorie.
    """
    category_field = f"{prefix}__categorie" if prefix else "categorie"
    name_field = f"{prefix}__nom" if prefix else "nom"
    legacy_names = (
        Q(**{f"{name_field}__icontains": "scolar"})
        | Q(**{f"{name_field}__icontains": "inscription"})
        | Q(**{f"{name_field}__icontains": "tranche"})
        | Q(**{f"{name_field}__icontains": "annuel"})
    )
    return Q(**{category_field: CATEGORIE_SCOLARITE}) | (
        Q(**{category_field: CATEGORIE_AUTO}) & legacy_names
    )
