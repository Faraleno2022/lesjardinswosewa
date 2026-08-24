"""
Version de l'application, source unique.

Le numero doit rester d'accord entre trois endroits : l'installateur Windows,
ce qui est affiche a l'utilisateur, et la comparaison avec la version publiee
sur le serveur. Une divergence proposerait une mise a jour deja installee, ou
pire, en cacherait une disponible. `build_exe.py` recopie donc cette valeur
dans `installer_myschool.iss` au moment de la compilation, plutot que de
laisser deux nombres vivre chacun de leur cote.
"""

APP_VERSION = '1.3.1'


def numero_de_version(valeur):
    """
    Traduit "1.10.2" en (1, 10, 2), comparable numeriquement.

    Une comparaison de chaines placerait "1.9.0" apres "1.10.0" : la dixieme
    version corrective ne serait jamais proposee aux postes.
    """
    morceaux = []
    for partie in str(valeur or '').strip().split('.'):
        chiffres = ''.join(c for c in partie if c.isdigit())
        morceaux.append(int(chiffres) if chiffres else 0)
    while len(morceaux) < 3:
        morceaux.append(0)
    return tuple(morceaux)


def est_plus_recente(candidate, reference=APP_VERSION):
    """Vrai si `candidate` est une version posterieure a `reference`."""
    if not candidate:
        return False
    return numero_de_version(candidate) > numero_de_version(reference)
