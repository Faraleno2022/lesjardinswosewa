"""
Fonctions utilitaires pour les bulletins maternelle.
Centralisées ici pour éviter la duplication de code.
"""


def lettre_vers_note(lettre):
    """Convertit une lettre d'appréciation en note sur 10"""
    conversion = {'A+': 10, 'A': 9.5, 'B+': 8.5, 'B': 7, 'B-': 6, 'C': 5.5, 'D': 3.5}
    return conversion.get(lettre, None)


def note_vers_lettre(note):
    """Convertit une note sur 10 en lettre d'appréciation"""
    if note is None:
        return None
    if note >= 10:
        return 'A+'
    if note >= 9.5:
        return 'A'
    if note >= 8:
        return 'B+'
    if note >= 7:
        return 'B'
    if note >= 6:
        return 'B-'
    if note >= 5:
        return 'C'
    return 'D'
