"""Règles de tarification liées à la garde prolongée (au-delà des heures de cours).

L'école peut garder certains élèves après les heures de cours, le temps que les
parents viennent les récupérer en sortant du travail. Ces élèves basculent alors
sur un tarif de scolarité annuelle forfaitaire, différent selon leur cycle.
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

MONTANT_GARDE_PROLONGEE_MATERNELLE_GARDERIE = Decimal('2700000')
MONTANT_GARDE_PROLONGEE_PRIMAIRE = Decimal('2800000')


def montant_scolarite_garde_prolongee(niveau):
    """Retourne le montant forfaitaire annuel de scolarité (GNF) pour un élève en
    garde prolongée, selon son niveau, ou ``None`` si ce niveau n'est pas concerné
    par cette option (collège, lycée, terminale...).
    """
    if not niveau:
        return None
    if niveau in NIVEAUX_MATERNELLE_GARDERIE:
        return MONTANT_GARDE_PROLONGEE_MATERNELLE_GARDERIE
    if niveau in NIVEAUX_PRIMAIRE:
        return MONTANT_GARDE_PROLONGEE_PRIMAIRE
    return None


def repartir_scolarite_forfait(montant_forfait, t1, t2, t3):
    """Répartit ``montant_forfait`` sur 3 tranches en conservant, quand c'est possible,
    la même proportion que la répartition d'origine (t1, t2, t3) de la grille tarifaire.
    Retourne un tuple (t1, t2, t3) de type Decimal dont la somme vaut ``montant_forfait``.
    """
    montant_forfait = Decimal(montant_forfait)
    t1 = Decimal(t1 or 0)
    t2 = Decimal(t2 or 0)
    t3 = Decimal(t3 or 0)
    total_origine = t1 + t2 + t3

    if total_origine > 0:
        nouveau_t1 = (montant_forfait * t1 / total_origine).quantize(Decimal('1'))
        nouveau_t2 = (montant_forfait * t2 / total_origine).quantize(Decimal('1'))
        nouveau_t3 = montant_forfait - nouveau_t1 - nouveau_t2
    else:
        base = (montant_forfait / 3).quantize(Decimal('1'))
        nouveau_t1 = base
        nouveau_t2 = base
        nouveau_t3 = montant_forfait - (2 * base)

    return nouveau_t1, nouveau_t2, nouveau_t3
