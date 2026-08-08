"""Règles de tarification liées à la garde prolongée (au-delà des heures de cours).

L'école peut garder certains élèves après les heures de cours, le temps que les
parents viennent les récupérer en sortant du travail. La scolarité annuelle de
ces élèves (les 3 tranches) bascule alors sur un forfait dépendant du cycle :

    Crèche, TPS, PS, MS, GS, Garderie ....... 2 700 000 GNF
    Primaire (1ère à 6ème) .................. 2 800 000 GNF
    Collège 10ème (fins de révision) ........ 2 850 000 GNF

Les frais d'inscription ou de réinscription **s'ajoutent** à ce forfait : ils
restent lus dans la grille tarifaire du niveau (par exemple 50 000 GNF à
l'inscription et 30 000 GNF à la réinscription en maternelle et au primaire,
70 000 / 50 000 en 10ème année) et ne sont jamais absorbés par le forfait.

Total dû pour l'année = forfait + frais d'inscription (ou de réinscription).
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
    """Retourne le forfait annuel de SCOLARITÉ (GNF) d'un élève en garde
    prolongée, selon son niveau, ou ``None`` si ce niveau n'est pas concerné.

    Ce montant couvre les 3 tranches. Les frais d'inscription ou de
    réinscription s'y ajoutent, ils n'en font pas partie.
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


def calculer_montants_garde_prolongee(niveau, t1, t2, t3):
    """Calcule les 3 tranches dues par un élève en garde prolongée : leur somme
    vaut le forfait annuel de son niveau.

    Les frais d'inscription/réinscription ne sont **pas** concernés : ils restent
    ceux de la grille tarifaire et viennent s'ajouter à ce forfait.

    Retourne ``None`` si le niveau n'est pas concerné par la garde prolongée
    (le calcul habituel de la grille doit alors s'appliquer), sinon un tuple
    (t1, t2, t3).
    """
    montant_forfait = montant_scolarite_garde_prolongee(niveau)
    if montant_forfait is None:
        return None
    return repartir_scolarite_forfait(montant_forfait, t1, t2, t3)
