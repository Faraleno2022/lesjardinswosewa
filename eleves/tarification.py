"""Règles de tarification liées à la garde prolongée (au-delà des heures de cours).

L'école peut garder certains élèves après les heures de cours, le temps que les
parents viennent les récupérer en sortant du travail. Ces élèves basculent alors
sur un tarif annuel GLOBAL forfaitaire (frais d'inscription/réinscription compris),
différent selon leur cycle.
"""
from decimal import Decimal

# Niveaux couverts par le forfait "maternelle/garderie"
NIVEAUX_MATERNELLE_GARDERIE = {
    'GARDERIE',
    'CRECHE',
    'TOUTE_PETITE_SECTION',
    'PETITE_SECTION',
    'MOYENNE_SECTION',
    'GRANDE_SECTION',
    'MATERNELLE',
}

# Niveaux couverts par le forfait "primaire"
NIVEAUX_PRIMAIRE = {
    'PRIMAIRE_1',
    'PRIMAIRE_2',
    'PRIMAIRE_3',
    'PRIMAIRE_4',
    'PRIMAIRE_5',
    'PRIMAIRE_6',
}

# Seule la 10ème (dernière année du collège) reste gardée, pour les fins de révision
NIVEAUX_COLLEGE_FIN_REVISION = {
    'COLLEGE_10',
}

MONTANT_GARDE_PROLONGEE_MATERNELLE_GARDERIE = Decimal('2700000')
MONTANT_GARDE_PROLONGEE_PRIMAIRE = Decimal('2800000')
MONTANT_GARDE_PROLONGEE_COLLEGE_10 = Decimal('2850000')


def montant_scolarite_garde_prolongee(niveau):
    """Retourne le montant GLOBAL forfaitaire annuel (GNF), frais d'inscription ou
    de réinscription compris, pour un élève en garde prolongée, selon son niveau,
    ou ``None`` si ce niveau n'est pas concerné par cette option.
    """
    if not niveau:
        return None
    if niveau in NIVEAUX_MATERNELLE_GARDERIE:
        return MONTANT_GARDE_PROLONGEE_MATERNELLE_GARDERIE
    if niveau in NIVEAUX_PRIMAIRE:
        return MONTANT_GARDE_PROLONGEE_PRIMAIRE
    if niveau in NIVEAUX_COLLEGE_FIN_REVISION:
        return MONTANT_GARDE_PROLONGEE_COLLEGE_10
    return None


def repartir_scolarite_forfait(montant_tranches, t1, t2, t3):
    """Répartit ``montant_tranches`` sur 3 tranches en conservant, quand c'est possible,
    la même proportion que la répartition d'origine (t1, t2, t3) de la grille tarifaire.
    Retourne un tuple (t1, t2, t3) de type Decimal dont la somme vaut ``montant_tranches``.
    """
    montant_tranches = Decimal(montant_tranches)
    t1 = Decimal(t1 or 0)
    t2 = Decimal(t2 or 0)
    t3 = Decimal(t3 or 0)
    total_origine = t1 + t2 + t3

    if total_origine > 0:
        nouveau_t1 = (montant_tranches * t1 / total_origine).quantize(Decimal('1'))
        nouveau_t2 = (montant_tranches * t2 / total_origine).quantize(Decimal('1'))
        nouveau_t3 = montant_tranches - nouveau_t1 - nouveau_t2
    else:
        base = (montant_tranches / 3).quantize(Decimal('1'))
        nouveau_t1 = base
        nouveau_t2 = base
        nouveau_t3 = montant_tranches - (2 * base)

    return nouveau_t1, nouveau_t2, nouveau_t3


def calculer_montants_garde_prolongee(niveau, frais_inscription_ou_reinscription, t1, t2, t3):
    """Calcule les montants dus (frais d'inscription/réinscription + 3 tranches) pour
    un élève en garde prolongée, de sorte que le TOTAL GLOBAL (frais compris) soit
    exactement le forfait annuel du niveau.

    ``frais_inscription_ou_reinscription`` est le montant déjà déterminé par
    l'appelant selon qu'il s'agit d'une inscription ou d'une réinscription : il
    n'est jamais ignoré, seulement déduit du forfait pour obtenir les tranches.

    Retourne ``None`` si le niveau n'est pas concerné par le forfait (le
    calcul habituel doit alors s'appliquer), sinon un tuple (t1, t2, t3).
    """
    montant_forfait = montant_scolarite_garde_prolongee(niveau)
    if montant_forfait is None:
        return None
    fi = Decimal(frais_inscription_ou_reinscription or 0)
    montant_tranches = max(montant_forfait - fi, Decimal('0'))
    return repartir_scolarite_forfait(montant_tranches, t1, t2, t3)
