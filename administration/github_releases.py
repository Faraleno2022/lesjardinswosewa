"""
Lecture des publications GitHub comme source des versions de l'application.

Jusqu'ici, diffuser une nouvelle version demandait de saisir a la main, dans
l'administration, son numero, son adresse et son empreinte SHA-256 — alors que
la publication GitHub porte deja ces trois informations, l'empreinte comprise
(GitHub la calcule lui-meme et l'expose dans son API). Une release publiee mais
non ressaisie restait donc invisible des postes, sans que rien ne le signale.

Ce module fait le pont. Il est volontairement lisible depuis deux endroits :

  - le serveur en ligne, qui recopie les releases dans `VersionApplication` et
    reste l'autorite (depublier une version defectueuse doit l'arreter partout) ;
  - un poste hors ligne, quand son serveur est injoignable — ou quand il n'a
    jamais ete relie a un serveur. Sans ce recours, une panne du site figerait
    tous les postes sur leur version du moment.

Rien ici ne fait confiance a GitHub sur parole : l'empreinte lue est ce qui
sera verifie avant de lancer l'installateur, et une release qui n'en fournit
pas est ignoree plutot qu'installee sans controle.
"""
import json
import logging
import re
import threading
from urllib import request as urlrequest

logger = logging.getLogger(__name__)

API = 'https://api.github.com'

# Depot par defaut, defini ici et non dans les settings : le module doit
# fonctionner tel quel sur un poste installe, dont le fichier de configuration
# ne parle que de synchronisation.
DEPOT_PAR_DEFAUT = 'Faraleno2022/lesjardinswosewa'

DELAI = 20

# Un poste ne doit pas rester bloque sur une reponse anormalement longue.
TAILLE_MAX_REPONSE = 4 * 1024 * 1024
TAILLE_MAX_EMPREINTE = 4096

# "desktop-v1.3.2" -> "1.3.2". Le prefixe du tag n'est pas impose : seul le
# groupe de nombres compte.
MOTIF_VERSION = re.compile(r'(\d+(?:\.\d+)+)')
MOTIF_EMPREINTE = re.compile(r'\b([0-9a-fA-F]{64})\b')
MOTIF_EMPREINTE_SEULE = re.compile(r'^[0-9a-fA-F]{64}$')


def _depot():
    from django.conf import settings
    return (
        getattr(settings, 'MYSCHOOL_GITHUB_REPO', '') or DEPOT_PAR_DEFAUT
    ).strip().strip('/')


def _entetes(authentifie=True):
    from django.conf import settings

    entetes = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        # GitHub refuse les appels sans identification du client.
        'User-Agent': 'MySchoolGN',
    }
    jeton = (getattr(settings, 'MYSCHOOL_GITHUB_TOKEN', '') or '').strip()
    if authentifie and jeton:
        # Facultatif : releve le quota anonyme de 60 appels par heure et par
        # adresse IP, qui est partage sur un hebergement mutualise.
        entetes['Authorization'] = f'Bearer {jeton}'
    return entetes


def _lire(url, *, json_attendu=True, authentifie=True, taille_max=TAILLE_MAX_REPONSE):
    if not url.lower().startswith('https://'):
        raise ValueError('Adresse GitHub non securisee.')
    requete = urlrequest.Request(url, headers=_entetes(authentifie), method='GET')
    with urlrequest.urlopen(requete, timeout=DELAI) as reponse:
        contenu = reponse.read(taille_max)
    return json.loads(contenu.decode('utf-8')) if json_attendu else contenu


def _version_du_tag(tag):
    trouve = MOTIF_VERSION.search(str(tag or ''))
    return trouve.group(1) if trouve else ''


def _empreinte(actif, actifs):
    """
    Empreinte SHA-256 de l'installateur, ou chaine vide.

    Deux sources, dans l'ordre : celle que GitHub calcule lui-meme a la mise en
    ligne (champ `digest`), puis le fichier `.sha256` depose a cote par le
    script de publication, pour les releases anterieures a ce champ.
    """
    digest = str(actif.get('digest') or '')
    if digest.lower().startswith('sha256:'):
        candidate = digest.split(':', 1)[1].strip().lower()
        if MOTIF_EMPREINTE_SEULE.match(candidate):
            return candidate

    voisin = next(
        (a for a in actifs if (a.get('name') or '') == f"{actif.get('name')}.sha256"),
        None,
    )
    if not voisin:
        return ''
    try:
        # Sans en-tete d'autorisation : l'adresse de telechargement redirige
        # vers un stockage signe, qui rejette une seconde authentification.
        contenu = _lire(
            voisin.get('browser_download_url') or '',
            json_attendu=False, authentifie=False, taille_max=TAILLE_MAX_EMPREINTE,
        )
    except Exception as erreur:
        logger.warning("[MAJ] Empreinte voisine illisible : %s", erreur)
        return ''
    trouve = MOTIF_EMPREINTE.search(contenu.decode('utf-8', 'ignore'))
    return trouve.group(1).lower() if trouve else ''


def _descripteur(release):
    """Traduit une release GitHub en descripteur de version, ou None."""
    tag = release.get('tag_name') or ''
    version = _version_du_tag(tag)
    if not version:
        return None

    actifs = release.get('assets') or []
    installateurs = [
        a for a in actifs if (a.get('name') or '').lower().endswith('.exe')
    ]
    if not installateurs:
        return None
    actif = next(
        (a for a in installateurs if version in (a.get('name') or '')),
        installateurs[0],
    )

    url = actif.get('browser_download_url') or ''
    if not url.lower().startswith('https://'):
        return None

    empreinte = _empreinte(actif, actifs)
    if not empreinte:
        # Le poste telecharge un executable et va le lancer. Sans empreinte, il
        # n'existe aucun moyen de verifier que c'est bien ce fichier-la : la
        # release est ignoree, jamais installee a l'aveugle.
        logger.warning(
            "[MAJ] Release %s ignoree : aucune empreinte SHA-256 publiee.", tag,
        )
        return None

    return {
        'version': version,
        'tag': tag,
        'url': url,
        'sha256': empreinte,
        'taille_octets': actif.get('size') or None,
        'notes': (release.get('body') or '').strip(),
    }


def versions_disponibles(limite=10):
    """
    Descripteurs des versions publiees sur GitHub.

    Les brouillons et les pre-publications sont ecartes : ce sont precisement
    les etats qui signalent « pas encore pour les utilisateurs ».
    """
    depot = _depot()
    if not depot:
        return []
    releases = _lire(f'{API}/repos/{depot}/releases?per_page={int(limite)}')
    descripteurs = []
    for release in releases or []:
        if release.get('draft') or release.get('prerelease'):
            continue
        descripteur = _descripteur(release)
        if descripteur:
            descripteurs.append(descripteur)
    return descripteurs


def derniere_version_github(limite=10):
    """
    Le descripteur de numero le plus eleve, pas la release la plus recente.

    Republier un correctif sur une branche ancienne ne doit pas faire
    redescendre les postes d'une version.
    """
    from ecole_moderne.version import numero_de_version

    descripteurs = versions_disponibles(limite)
    if not descripteurs:
        return None
    return max(descripteurs, key=lambda d: numero_de_version(d['version']))


# ─── Recopie vers la base du serveur ─────────────────────────────────────────
def importer_versions(limite=10):
    """
    Recopie les releases GitHub dans `VersionApplication`.

    Retourne (creees, mises_a_jour). Ne leve jamais : une panne de GitHub ne
    doit pas empecher le serveur de repondre aux postes avec ce qu'il connait
    deja.

    Une version deja connue voit son adresse, son empreinte et ses notes
    rafraichies, mais jamais son indicateur de publication. Decocher la case
    est la seule facon d'arreter la diffusion d'une version defectueuse : un
    import qui la recocherait la relancerait sur tous les postes.
    """
    from django.core.exceptions import ValidationError

    from .models import VersionApplication

    try:
        descripteurs = versions_disponibles(limite)
    except Exception as erreur:
        logger.warning('[MAJ] Lecture des releases GitHub impossible : %s', erreur)
        return 0, 0

    creees = modifiees = 0
    for descripteur in descripteurs:
        existante = VersionApplication.objects.filter(
            version=descripteur['version'],
        ).first()

        if existante is None:
            version = VersionApplication(
                version=descripteur['version'],
                url_telechargement=descripteur['url'],
                sha256=descripteur['sha256'],
                taille_octets=descripteur['taille_octets'],
                notes=descripteur['notes'],
                # Publier une release EST l'acte de mise a disposition : la
                # redemander ici dupliquerait ce geste sur un second ecran, et
                # c'est exactement l'oubli qui laissait des versions publiees
                # invisibles des postes.
                publiee=True,
            )
            try:
                version.full_clean()
            except ValidationError as erreur:
                logger.warning(
                    '[MAJ] Release %s ignoree : %s', descripteur['tag'], erreur,
                )
                continue
            version.save()
            creees += 1
            logger.info(
                '[MAJ] Version %s importee depuis GitHub.', descripteur['version'],
            )
            continue

        champs = []
        for champ, valeur in (
            ('url_telechargement', descripteur['url']),
            ('sha256', descripteur['sha256']),
            ('taille_octets', descripteur['taille_octets']),
            ('notes', descripteur['notes']),
        ):
            if getattr(existante, champ) != valeur:
                setattr(existante, champ, valeur)
                champs.append(champ)
        if champs:
            existante.save(update_fields=champs)
            modifiees += 1

    return creees, modifiees


# ─── Import declenche par le trafic ──────────────────────────────────────────
CLE_VERROU = 'majgithub:dernier-import'
DELAI_ENTRE_IMPORTS = 15 * 60


def _import_automatique_actif():
    from django.conf import settings
    return bool(getattr(settings, 'MYSCHOOL_GITHUB_AUTO_IMPORT', True))


def importer_si_necessaire():
    """
    Rafraichit la liste des versions, au plus une fois par quart d'heure.

    Sans cela, publier une release sur GitHub resterait sans effet tant que
    personne ne lance la commande a la main — le travail manuel que ce
    mecanisme existe pour supprimer. Le verrou evite qu'une centaine de postes
    ne provoque une centaine d'appels a GitHub, dont le quota anonyme est de
    60 requetes par heure et par adresse IP, partagee sur un hebergement
    mutualise.
    """
    if not _import_automatique_actif():
        return False
    from django.core.cache import cache

    # `add` n'ecrit que si la cle est absente : le premier appel de la periode
    # passe, les suivants repartent immediatement.
    if not cache.add(CLE_VERROU, 1, DELAI_ENTRE_IMPORTS):
        return False
    importer_versions()
    return True


def _importer_puis_liberer():
    """Import execute hors requete. Ferme sa connexion : elle lui est propre."""
    from django.db import connection

    try:
        importer_versions()
    except Exception:
        logger.warning('[MAJ] Import GitHub en arriere-plan interrompu.', exc_info=True)
    finally:
        connection.close()


def declencher_import_en_arriere_plan():
    """
    Lance l'import sans faire attendre l'appelant.

    Un poste qui demande s'il existe une mise a jour ne doit pas voir sa
    requete retenue le temps d'un aller-retour vers GitHub : sur un
    hebergement mutualise, chaque requete en cours immobilise un des rares
    processus qui servent aussi le site public. Et rien ne presse — un poste
    ne repose la question que toutes les six heures.
    """
    if not _import_automatique_actif():
        return False
    from django.core.cache import cache

    if not cache.add(CLE_VERROU, 1, DELAI_ENTRE_IMPORTS):
        return False

    fil = threading.Thread(
        target=_importer_puis_liberer, name='import-versions-github', daemon=True,
    )
    fil.start()
    return True
