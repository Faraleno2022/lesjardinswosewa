"""
Mise a jour automatique de l'application Windows.

Un poste installe chez un utilisateur ne doit pas dependre de quelqu'un qui
passe avec une cle USB. Ce module lui fait recuperer les nouvelles versions
tout seul :

1. un fil d'arriere-plan demande periodiquement au serveur en ligne s'il
   existe une version plus recente ;
2. si oui, l'installateur est telecharge en tache de fond, sans deranger le
   travail en cours ;
3. son empreinte SHA-256 est verifiee. Elle ne l'est pas seulement apres le
   telechargement mais aussi juste avant le lancement, car c'est la, et la
   seule, que le fichier devient du code execute ;
4. l'installation a lieu au demarrage suivant de l'application. C'est le seul
   moment ou personne n'est en train de saisir : l'installateur ferme
   l'application pour remplacer ses fichiers, et couper une saisie en cours
   pour installer une mise a jour serait payer trop cher un gain de quelques
   heures.

La configuration reprend celle de la synchronisation (`sync_config.json`) :
un poste sait deja a quel serveur il se rattache, avec quels identifiants.
"""
import hashlib
import json
import logging
import os
import subprocess
import sys
import threading
import time
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .version import APP_VERSION, est_plus_recente

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

# Taille des morceaux lus pendant le telechargement et le calcul d'empreinte.
TAILLE_BLOC = 256 * 1024

# Un installateur depasse la centaine de megaoctets sur une liaison lente :
# mieux vaut un long telechargement qui aboutit qu'un delai qui l'interrompt
# a chaque tentative.
DELAI_TELECHARGEMENT = 60 * 30

# Garde-fou : au-dela, ce n'est plus l'installateur attendu.
TAILLE_MAX_OCTETS = 1024 * 1024 * 1024


def _dossier_mises_a_jour():
    base = os.environ.get('MYSCHOOL_BASE_DIR') or os.getcwd()
    return os.path.join(base, 'mises_a_jour')


def _fichier_descripteur():
    return os.path.join(_dossier_mises_a_jour(), 'en_attente.json')


def _config():
    """Retourne (serveur, device_id, token) ou None si le poste n'est pas relie."""
    try:
        from django.conf import settings
    except Exception:
        return None
    serveur = (getattr(settings, 'MYSCHOOL_SYNC_SERVER_URL', '') or '').rstrip('/')
    device_id = getattr(settings, 'MYSCHOOL_SYNC_DEVICE_ID', '') or ''
    token = getattr(settings, 'MYSCHOOL_SYNC_TOKEN', '') or ''
    if serveur and device_id and token:
        return serveur, device_id, token
    return None


# ─── Empreinte ────────────────────────────────────────────────────────────────
def empreinte_fichier(chemin):
    """SHA-256 d'un fichier, lu par morceaux (il pese des centaines de Mo)."""
    condensat = hashlib.sha256()
    with open(chemin, 'rb') as fichier:
        for bloc in iter(lambda: fichier.read(TAILLE_BLOC), b''):
            condensat.update(bloc)
    return condensat.hexdigest()


# ─── Interrogation du serveur ─────────────────────────────────────────────────
def _demander_derniere_version(serveur, device_id, token):
    if urlparse(serveur).scheme != 'https':
        raise ValueError("L'adresse du serveur de mises a jour doit etre en https.")
    url = f'{serveur}/api/v1/updates/latest/?version={APP_VERSION}'
    requete = urlrequest.Request(
        url,
        headers={
            'X-Sync-Device': device_id,
            'X-Sync-Token': token,
            'Accept': 'application/json',
        },
        method='GET',
    )
    with urlrequest.urlopen(requete, timeout=30) as reponse:
        return json.loads(reponse.read().decode('utf-8'))


# ─── Telechargement ───────────────────────────────────────────────────────────
def _telecharger(url, destination, taille_attendue=None):
    """
    Ecrit le fichier distant dans `destination`.

    Le telechargement passe par un fichier temporaire renomme a la fin : une
    coupure de courant laisserait sinon un installateur tronque que le
    demarrage suivant prendrait pour complet.
    """
    if urlparse(url).scheme != 'https':
        raise ValueError("L'adresse de telechargement doit etre en https.")

    partiel = destination + '.part'
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    recu = 0
    with urlrequest.urlopen(url, timeout=DELAI_TELECHARGEMENT) as reponse:
        # urllib suit les redirections automatiquement. Une URL HTTPS qui
        # redirigerait vers HTTP ne doit pas contourner l'exigence de transport
        # chiffre verifiee ci-dessus.
        url_finale = reponse.geturl() if hasattr(reponse, 'geturl') else url
        if urlparse(url_finale).scheme != 'https':
            raise ValueError("La redirection de telechargement doit rester en https.")
        with open(partiel, 'wb') as sortie:
            while True:
                bloc = reponse.read(TAILLE_BLOC)
                if not bloc:
                    break
                recu += len(bloc)
                if recu > TAILLE_MAX_OCTETS:
                    raise ValueError('Fichier anormalement volumineux.')
                sortie.write(bloc)

    if taille_attendue and recu != int(taille_attendue):
        os.remove(partiel)
        raise ValueError(
            f'Taille inattendue : {recu} octets recus, {taille_attendue} annonces.'
        )

    os.replace(partiel, destination)
    return recu


def _nettoyer(dossier, sauf=None):
    """Efface les installateurs qui ne servent plus."""
    try:
        for nom in os.listdir(dossier):
            chemin = os.path.join(dossier, nom)
            if chemin == sauf or nom == os.path.basename(_fichier_descripteur()):
                continue
            if os.path.isfile(chemin):
                os.remove(chemin)
    except Exception:
        pass


def _demander_github():
    """
    Descripteur de la derniere publication GitHub, sans passer par le serveur.

    Recours pour un poste dont le serveur est injoignable, ou qui n'a jamais
    ete relie a un serveur : sans lui, une panne du site — ou une installation
    autonome — figerait la machine sur sa version du moment.
    """
    try:
        from administration import github_releases
    except Exception:
        return None

    try:
        descripteur = github_releases.derniere_version_github()
    except Exception as erreur:
        logger.warning('[MAJ] Lecture des publications GitHub impossible : %s', erreur)
        return None

    if not descripteur or not est_plus_recente(descripteur['version']):
        return None

    logger.info(
        '[MAJ] Version %s trouvee sur GitHub (serveur injoignable).',
        descripteur['version'],
    )
    return {
        'ok': True,
        'mise_a_jour_disponible': True,
        'version': descripteur['version'],
        'url': descripteur['url'],
        'sha256': descripteur['sha256'],
        'taille_octets': descripteur.get('taille_octets'),
        'notes': descripteur.get('notes') or '',
        # Une version n'est imposee que par decision explicite du serveur.
        # GitHub ne porte pas cette nuance, et un poste coupe du serveur est
        # justement celui a qui on ne veut rien imposer.
        'obligatoire': False,
    }


def _descripteur_distant():
    """
    Ce qu'il y a a installer, ou None.

    Le serveur de l'ecole est interroge en premier : c'est lui qui porte la
    decision. Depublier une version defectueuse doit l'arreter partout, donc
    un « rien de neuf » de sa part est definitif — aller demander a GitHub
    par-dessus annulerait ce geste. GitHub n'intervient que quand le serveur
    n'a pas repondu du tout.
    """
    configuration = _config()
    if not configuration:
        # Poste autonome, jamais relie a un serveur.
        return _demander_github()

    serveur, device_id, token = configuration
    try:
        reponse = _demander_derniere_version(serveur, device_id, token)
    except HTTPError as erreur:
        # Le serveur a bien repondu, par un refus : ce poste n'est plus
        # autorise. Ce n'est pas une panne de reseau, et contourner ce refus
        # par GitHub reviendrait a servir une machine revoquee.
        logger.warning(
            '[MAJ] Verification refusee par le serveur (HTTP %s). '
            'Verifiez que ce poste est toujours autorise.',
            erreur.code,
        )
        return None
    except (URLError, OSError, ValueError) as erreur:
        logger.warning(
            '[MAJ] Serveur injoignable (%s) : lecture directe de GitHub.', erreur,
        )
        return _demander_github()
    except Exception as erreur:
        logger.warning(
            '[MAJ] Verification impossible (%s) : lecture directe de GitHub.', erreur,
        )
        return _demander_github()

    if not reponse.get('ok') or not reponse.get('mise_a_jour_disponible'):
        return None
    return reponse


def preparer_mise_a_jour():
    """
    Une passe complete : interroge, telecharge, verifie, enregistre.

    Retourne le numero de version preparee, ou None. Ne leve jamais : hors
    ligne ou serveur muet, le poste reessaiera plus tard.
    """
    reponse = _descripteur_distant()
    if not reponse:
        return None

    version = reponse.get('version')
    url = reponse.get('url')
    empreinte_attendue = (reponse.get('sha256') or '').strip().lower()
    if not version or not url or len(empreinte_attendue) != 64:
        logger.warning('[MAJ] Descripteur de version incomplet, ignore.')
        return None
    if not est_plus_recente(version):
        return None

    dossier = _dossier_mises_a_jour()
    destination = os.path.join(dossier, f'MySchoolGN_Setup_v{version}.exe')

    # Deja telechargee lors d'une session precedente : inutile de recommencer.
    if os.path.exists(destination):
        try:
            if empreinte_fichier(destination) == empreinte_attendue:
                _enregistrer_descripteur(version, destination, empreinte_attendue, reponse)
                return version
            os.remove(destination)
        except Exception:
            return None

    try:
        logger.info('[MAJ] Telechargement de la version %s...', version)
        _telecharger(url, destination, reponse.get('taille_octets'))
    except Exception as erreur:
        logger.warning('[MAJ] Telechargement interrompu : %s', erreur)
        return None

    try:
        obtenue = empreinte_fichier(destination)
    except Exception:
        return None

    if obtenue != empreinte_attendue:
        # Le fichier n'est pas celui annonce. On le supprime sans le garder
        # pour analyse : le laisser sur le disque, c'est laisser un
        # executable non identifie a portee d'un double-clic.
        os.remove(destination)
        logger.error(
            "[MAJ] Empreinte incorrecte pour la version %s : fichier supprime, "
            "aucune installation.", version,
        )
        return None

    _enregistrer_descripteur(version, destination, empreinte_attendue, reponse)
    _nettoyer(dossier, sauf=destination)
    logger.info('[MAJ] Version %s prete, elle sera installee au prochain demarrage.', version)
    return version


def _enregistrer_descripteur(version, chemin, empreinte, reponse):
    descripteur = {
        'version': version,
        'chemin': chemin,
        'sha256': empreinte,
        'notes': reponse.get('notes') or '',
        'obligatoire': bool(reponse.get('obligatoire')),
        'preparee_le': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    with open(_fichier_descripteur(), 'w', encoding='utf-8') as fichier:
        json.dump(descripteur, fichier, ensure_ascii=False, indent=2)


# ─── Installation ─────────────────────────────────────────────────────────────
def mise_a_jour_en_attente():
    """
    Le descripteur d'une mise a jour prete, ou None.

    L'empreinte est recalculee ici. Le fichier a pu etre remplace depuis son
    telechargement, et c'est le dernier point de controle avant de le lancer.
    """
    try:
        with open(_fichier_descripteur(), encoding='utf-8') as fichier:
            descripteur = json.load(fichier)
    except Exception:
        return None

    chemin = descripteur.get('chemin')
    version = descripteur.get('version')
    empreinte = (descripteur.get('sha256') or '').lower()
    if not chemin or not version or not os.path.isfile(chemin):
        return None
    if not est_plus_recente(version):
        # Deja installee : le descripteur a survecu a la mise a jour.
        oublier_mise_a_jour()
        return None

    try:
        if empreinte_fichier(chemin) != empreinte:
            logger.error('[MAJ] Installateur altere depuis son telechargement : ignore.')
            oublier_mise_a_jour(supprimer_fichier=True)
            return None
    except Exception:
        return None

    return descripteur


def oublier_mise_a_jour(supprimer_fichier=False):
    descripteur = None
    try:
        with open(_fichier_descripteur(), encoding='utf-8') as fichier:
            descripteur = json.load(fichier)
    except Exception:
        pass
    try:
        os.remove(_fichier_descripteur())
    except Exception:
        pass
    if supprimer_fichier and descripteur:
        try:
            os.remove(descripteur.get('chemin'))
        except Exception:
            pass


def installer_mise_a_jour(descripteur):
    """
    Lance l'installateur en mode silencieux et rend la main immediatement.

    `/RELANCE=1` demande a l'installateur de rouvrir l'application une fois
    les fichiers remplaces : en mode silencieux il ne le fait pas de lui-meme,
    et l'utilisateur qui vient de lancer MySchoolGN verrait sa fenetre ne
    jamais s'ouvrir.

    L'appelant doit quitter tout de suite apres : l'installateur ne peut pas
    remplacer un executable encore en cours d'utilisation.
    """
    if sys.platform != 'win32':
        return False
    chemin = descripteur.get('chemin')
    if not chemin or not os.path.isfile(chemin):
        return False

    try:
        journal = os.path.join(_dossier_mises_a_jour(), 'installation.log')
        subprocess.Popen(
            [
                chemin,
                '/VERYSILENT',
                '/SUPPRESSMSGBOXES',
                '/SP-',
                '/NOCANCEL',
                '/NORESTART',
                '/CLOSEAPPLICATIONS',
                '/FORCECLOSEAPPLICATIONS',
                f'/LOG={journal}',
                '/RELANCE=1',
            ],
            close_fds=True,
            creationflags=getattr(subprocess, 'DETACHED_PROCESS', 0)
            | getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0),
        )
    except Exception as erreur:
        logger.error("[MAJ] Impossible de lancer l'installateur : %s", erreur)
        return False

    # Le descripteur est retire maintenant : si l'installation echouait, le
    # demarrage suivant ne doit pas relancer indefiniment le meme installateur.
    oublier_mise_a_jour()
    logger.info('[MAJ] Installation de la version %s lancee.', descripteur.get('version'))
    return True


def appliquer_si_en_attente():
    """
    A appeler au tout debut du demarrage.

    Retourne True si une installation vient d'etre lancee : l'application doit
    alors s'arreter sans rien ouvrir.
    """
    try:
        descripteur = mise_a_jour_en_attente()
        if not descripteur:
            return False
        return installer_mise_a_jour(descripteur)
    except Exception:
        return False


# ─── Fil d'arriere-plan ───────────────────────────────────────────────────────
def _worker(intervalle, delai_initial):
    time.sleep(max(0, delai_initial))
    while True:
        try:
            preparer_mise_a_jour()
        except Exception:
            pass
        time.sleep(intervalle)


def start(intervalle: int = 6 * 3600, delai_initial: int = 90) -> bool:
    """
    Demarre la surveillance des mises a jour (idempotent).

    intervalle    : secondes entre deux verifications.
    delai_initial : attente avant la premiere, pour ne pas disputer la bande
                    passante au demarrage de l'application.
    """
    global _started
    if sys.platform != 'win32':
        return False
    with _lock:
        if _started:
            return False
        _started = True
    fil = threading.Thread(
        target=_worker, args=(max(600, intervalle), delai_initial),
        name='auto-mise-a-jour', daemon=True,
    )
    fil.start()
    return True
