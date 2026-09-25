"""Montants en toutes lettres pour les états et bulletins de paie."""

from decimal import Decimal, ROUND_HALF_UP

UNITES = (
    'zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit',
    'neuf', 'dix', 'onze', 'douze', 'treize', 'quatorze', 'quinze', 'seize',
    'dix-sept', 'dix-huit', 'dix-neuf',
)
DIZAINES = {
    2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante',
}


def _moins_de_cent(n):
    if n < 20:
        return UNITES[n]
    dizaine, unite = divmod(n, 10)
    if dizaine in (7, 9):
        base = 'soixante' if dizaine == 7 else 'quatre-vingt'
        reste = 10 + unite
        liaison = ' et ' if dizaine == 7 and unite == 1 else '-'
        return f"{base}{liaison}{UNITES[reste]}"
    if dizaine == 8:
        return 'quatre-vingts' if unite == 0 else f"quatre-vingt-{UNITES[unite]}"
    base = DIZAINES[dizaine]
    if unite == 0:
        return base
    if unite == 1:
        return f"{base} et un"
    return f"{base}-{UNITES[unite]}"


def _moins_de_mille(n, final=True):
    centaines, reste = divmod(n, 100)
    morceaux = []
    if centaines:
        if centaines == 1:
            morceaux.append('cent')
        else:
            pluriel = 's' if reste == 0 and final else ''
            morceaux.append(f"{UNITES[centaines]} cent{pluriel}")
    if reste:
        texte = _moins_de_cent(reste)
        if not final and texte == 'quatre-vingts':
            texte = 'quatre-vingt'
        morceaux.append(texte)
    return ' '.join(morceaux)


def nombre_en_lettres(n):
    n = int(n)
    if n < 0:
        return f"moins {nombre_en_lettres(-n)}"
    if n == 0:
        return UNITES[0]
    morceaux = []
    for valeur, singulier, pluriel in (
        (10 ** 9, 'milliard', 'milliards'),
        (10 ** 6, 'million', 'millions'),
    ):
        quantite, n = divmod(n, valeur)
        if quantite:
            morceaux.append(
                f"{nombre_en_lettres(quantite)} "
                f"{singulier if quantite == 1 else pluriel}"
            )
    milliers, n = divmod(n, 1000)
    if milliers:
        morceaux.append(
            'mille' if milliers == 1
            else f"{_moins_de_mille(milliers, final=False)} mille"
        )
    if n:
        morceaux.append(_moins_de_mille(n))
    return ' '.join(morceaux)


def montant_en_lettres(montant):
    """« 6 565 000 » -> « Six millions cinq cent soixante-cinq mille francs guinéens »."""
    entier = int(Decimal(str(montant or 0)).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
    texte = nombre_en_lettres(entier)
    return f"{texte[:1].upper()}{texte[1:]} francs guinéens"
