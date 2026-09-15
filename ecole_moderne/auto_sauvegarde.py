"""Sauvegarde automatique en arrière-plan (application Desktop).

Un thread daemon sauvegarde au démarrage si la dernière archive est trop
ancienne, puis à intervalle régulier tant que l'application tourne. C'est le
déclencheur qui ne demande rien à personne : ni tâche planifiée à créer, ni clé
à brancher un jour précis, ni droits administrateur.

Il complète — sans remplacer — la tâche planifiée Windows (voir
`Planifier_Sauvegarde.bat`), seule capable de sauvegarder machine allumée mais
application fermée.

La logique est appelée DIRECTEMENT (et non via `call_command`), comme pour
`synchronisation.auto_sync` : dans l'exécutable PyInstaller, la découverte des
commandes de management n'est pas garantie.
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

# Valeurs par défaut : une sauvegarde toutes les 6 h suffit à borner la perte à
# une demi-journée de saisie, sans peser sur le poste (archive ~10 Mo).
INTERVALLE_DEFAUT_HEURES = 6
DELAI_DEMARRAGE_SECONDES = 90


def _config_heures(config: dict) -> float:
    try:
        heures = float(config.get('MYSCHOOL_SAUVEGARDE_INTERVALLE_HEURES')
                       or INTERVALLE_DEFAUT_HEURES)
    except (TypeError, ValueError):
        heures = INTERVALLE_DEFAUT_HEURES
    return max(0.5, heures)


def _boucle(intervalle_heures: float, delai_demarrage: int) -> None:
    from . import sauvegarde

    time.sleep(delai_demarrage)
    while True:
        try:
            config = sauvegarde.charger_config()
            intervalle = timedelta(hours=intervalle_heures)
            derniere = sauvegarde.derniere_sauvegarde(config)
            if derniere is None or datetime.now() - derniere >= intervalle:
                rapport = sauvegarde.executer_sauvegarde(config=config)
                if rapport.succes:
                    logger.info('Sauvegarde automatique : %s', rapport.resume())
                else:
                    logger.warning('Sauvegarde automatique en echec : %s',
                                   rapport.erreur or 'cause inconnue')
        except Exception as err:  # le thread ne doit jamais tuer l'application
            logger.warning('Sauvegarde automatique interrompue : %s', err)

        # Réveil fréquent : la fenêtre de sauvegarde est ainsi respectée même si
        # le poste a été mis en veille entre deux cycles.
        time.sleep(min(30 * 60, max(300, int(intervalle_heures * 3600 / 4))))


def start(intervalle_heures: float | None = None,
          delai_demarrage: int = DELAI_DEMARRAGE_SECONDES) -> float:
    """Démarre le thread.

    Retourne l'intervalle retenu (en heures), ou 0 si la sauvegarde automatique
    est désactivée ou déjà lancée — de quoi afficher un message exact.
    """
    global _started

    from . import sauvegarde

    config = sauvegarde.charger_config()
    if str(config.get('MYSCHOOL_SAUVEGARDE_AUTO', '1')).lower() in {'0', 'false', 'non', 'no'}:
        return 0.0
    if os.environ.get('MYSCHOOL_SAUVEGARDE_AUTO', '').lower() in {'0', 'false'}:
        return 0.0

    with _lock:
        if _started:
            return 0.0
        heures = intervalle_heures if intervalle_heures else _config_heures(config)
        thread = threading.Thread(
            target=_boucle, args=(heures, delai_demarrage),
            name='auto-sauvegarde', daemon=True,
        )
        thread.start()
        _started = True
        return heures
