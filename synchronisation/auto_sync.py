"""
Synchronisation automatique en arriere-plan (application Desktop).

Un thread daemon envoie (push) periodiquement les changements locaux en attente
puis recupere (pull) ceux des autres postes, via le serveur EN LIGNE configure.
Hors-ligne, chaque tentative est reessayee a cadence rapprochee et tracee (sans
noyer le journal) : des que la connexion revient, la synchronisation reprend
automatiquement, sans action de l'utilisateur. `diagnostiquer_synchronisation()`
declenche un cycle unique et immediat, avec le detail complet d'un echec.

La logique push/pull est appelee DIRECTEMENT (et non via `call_command`) afin
de rester fiable dans l'executable PyInstaller, ou la decouverte des commandes
de management n'est pas garantie.

Configuration par machine (aucune recompilation) : fichier `sync_config.json`
charge par run_server.py -> reglages MYSCHOOL_SYNC_SERVER_URL / _ECOLE_ID /
_DEVICE_ID / _TOKEN. Voir `sync_config.example.json`.
"""
import gzip
import json
import logging
import os
import threading
import time
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)

_started = False
_lock = threading.Lock()

# Reveil immediat du worker. Le signal `post_save` le declenche des qu'une
# donnee est enregistree sur ce poste : l'envoi part dans la seconde au lieu
# d'attendre la fin du cycle en cours.
_wake = threading.Event()

# Horodatage du dernier echange non vide. Tant qu'il est recent, le poste
# reste en cadence rapide : une saisie arrive rarement seule, et c'est
# exactement le moment ou l'utilisateur attend de voir les donnees apparaitre.
_last_transfer = 0.0

# Duree pendant laquelle le poste reste en cadence rapide apres un echange.
HOT_WINDOW_SECONDS = 120

# Court delai avant l'envoi declenche par une saisie : une operation ecrit
# souvent plusieurs objets a la suite (un paiement, ses remises, l'echeancier),
# qui partent ainsi dans un seul lot.
DEBOUNCE_SECONDS = 1.0

# Echecs consecutifs d'un cycle de synchronisation, et date du dernier message
# trace a ce sujet. Sans ce compteur, un poste hors-ligne ou mal configure ne
# laisse litteralement aucune preuve dans les journaux : le worker reessaie en
# silence, cycle apres cycle, parfois pendant des jours, et le seul moyen de
# savoir pourquoi est de reproduire l'echec a la main sur le poste concerne.
_echecs_consecutifs = 0
_dernier_log_echec = 0.0

# Un poste hors-ligne reessaie toutes les quelques secondes : sans limite, ce
# seul message noierait le reste du journal. Le tout premier echec d'une serie
# est trace immediatement ; les suivants, au plus tous les 5 minutes tant que
# ca persiste.
INTERVALLE_LOG_ECHEC_SECONDES = 300

# Plafond de la cadence au repos, quelle que soit la configuration du poste.
#
# Au repos, un cycle ne coute qu'une lecture du filigrane : une requete sans
# corps, dont la reponse tient en trois nombres, et cote serveur un `MAX(id)`
# sur une colonne indexee. Rien la-dedans ne justifie de faire attendre
# quinze secondes une donnee saisie sur un autre poste. Ce plafond est donc
# ce qui borne reellement le delai d'apparition : au-dela du filigrane, le
# poste ne telecharge que s'il y a effectivement du nouveau.
MAX_IDLE_INTERVAL = 3

# Les payloads embarquent le contenu des fichiers : on borne le lot pousse par
# sa taille pour rester sous DATA_UPLOAD_MAX_MEMORY_SIZE (5 Mo) cote serveur.
MAX_PUSH_BYTES = 3 * 1024 * 1024

# Nombre d'echecs tolerees avant d'abandonner un changement : au-dela, la
# cause n'est plus temporaire. Sans cette borne, un changement irrecuperable
# est rejoue (ou repousse) a chaque cycle, indefiniment.
MAX_APPLY_ATTEMPTS = 5
MAX_PUSH_ATTEMPTS = 5

# Nombre de lots enchaines dans un meme cycle, a l'envoi comme a la reception.
#
# Le serveur ne sert que 200 changements par requete, et le poste n'en poussait
# qu'un lot par cycle. Un poste rentre apres plusieurs jours hors ligne
# rattrapait donc 200 changements toutes les quelques secondes : des minutes
# d'attente pendant lesquelles ses ecrans montrent des donnees incompletes,
# alors que le reseau est disponible et la file connue. On enchaine desormais
# les lots dans le meme cycle, en bornant la boucle pour qu'un rattrapage
# gigantesque ne monopolise pas indefiniment le fil d'arriere-plan.
MAX_LOTS_PAR_CYCLE = 25


# ─── Etat local (pull incremental) ────────────────────────────────────────────
def _state_path() -> str:
    base = os.environ.get('MYSCHOOL_BASE_DIR') or os.getcwd()
    return os.path.join(base, '.sync_state.json')


def _load_since_id():
    return _load_state().get('since_id')


def _load_state():
    try:
        with open(_state_path(), 'r', encoding='utf-8') as f:
            state = json.load(f)
            return state if isinstance(state, dict) else {}
    except Exception:
        return {}


def _save_since_id(value) -> None:
    if not value:
        return
    _save_state(since_id=value)


def _save_state(*, since_id=None, initial_done=None, school_sync_uuid=None) -> None:
    state = _load_state()
    if since_id:
        state['since_id'] = since_id
    if initial_done is not None:
        state['initial_done'] = bool(initial_done)
    if school_sync_uuid:
        state['school_sync_uuid'] = str(school_sync_uuid)
    try:
        with open(_state_path(), 'w', encoding='utf-8') as f:
            json.dump(state, f)
    except Exception:
        pass


# ─── Client HTTP ──────────────────────────────────────────────────────────────
def _request_json(url, device_id, token, payload=None, method='POST', timeout=45):
    body = None if payload is None else json.dumps(payload).encode('utf-8')
    req = urlrequest.Request(
        url,
        data=body,
        headers={
            'Content-Type': 'application/json',
            # Un lot de reception transporte jusqu'a 200 changements, contenu
            # des fichiers compris (photos d'eleves encodees en base64) : la
            # reponse se compte en megaoctets. Le serveur sait deja compresser
            # (GZipMiddleware), mais ne le fait que si le client le demande, et
            # `urllib` ne le demande pas de lui-meme. Sur les liaisons dont
            # dispose une ecole, c'est la difference entre quelques secondes et
            # une minute.
            'Accept-Encoding': 'gzip',
            'X-Sync-Device': device_id,
            'X-Sync-Token': token,
        },
        method=method,
    )
    with urlrequest.urlopen(req, timeout=timeout) as response:
        brut = response.read()
        if (response.headers.get('Content-Encoding') or '').lower() == 'gzip':
            brut = gzip.decompress(brut)
        return json.loads(brut.decode('utf-8'))


# ─── Configuration ────────────────────────────────────────────────────────────
def _config():
    """Retourne (server, device_id, token, ecole_id) ou None si incomplet."""
    try:
        from django.conf import settings
    except Exception:
        return None
    server = (getattr(settings, 'MYSCHOOL_SYNC_SERVER_URL', '') or '').rstrip('/')
    device_id = getattr(settings, 'MYSCHOOL_SYNC_DEVICE_ID', '') or ''
    token = getattr(settings, 'MYSCHOOL_SYNC_TOKEN', '') or ''
    ecole_id = getattr(settings, 'MYSCHOOL_SYNC_ECOLE_ID', '') or ''
    if server and device_id and token and ecole_id:
        return server, device_id, token, ecole_id
    return None


def _is_configured() -> bool:
    return _config() is not None


def notify_local_change() -> None:
    """Reveille le worker : une donnee vient d'etre enregistree localement."""
    _wake.set()


def _mark_transfer() -> None:
    global _last_transfer
    _last_transfer = time.monotonic()


def _is_hot() -> bool:
    return (time.monotonic() - _last_transfer) < HOT_WINDOW_SECONDS


# ─── Une passe de synchronisation ─────────────────────────────────────────────
def _log_abandon(change, phase: str) -> None:
    """
    Trace un abandon : c'est le seul cas ou une donnee cesse d'etre propagee.

    Silencieux, il produirait une divergence invisible entre les postes.
    """
    logger.warning(
        "[Sync] Changement abandonne apres %s tentatives (%s) : %s %s %s -> %s",
        change.tentatives, phase, change.operation, change.model_label,
        change.object_uuid, change.erreur,
    )


def _push(server, device_id, token, ecole, apres_id=0):
    """
    Envoie un lot de changements locaux. Retourne (nombre_accepte, curseur).

    `apres_id` / le curseur retourne permettent a l'appelant d'enchainer
    plusieurs lots dans un meme cycle sans jamais representer un changement
    deja soumis. C'est indispensable : un refus laisse la ligne en attente
    avec un id bas, et une simple boucle la reprendrait a chaque tour,
    epuisant en quelques millisecondes le budget de tentatives prevu pour
    s'etaler sur plusieurs cycles — le temps que la dependance manquante
    arrive.
    """
    from django.utils import timezone
    from .models import SyncChange
    pending = list(
        SyncChange.objects
        .filter(
            ecole=ecole,
            statut=SyncChange.STATUT_PENDING,
            tentatives__lt=MAX_PUSH_ATTEMPTS,
            id__gt=apres_id,
        )
        .order_by('id')[:200]
    )
    if not pending:
        return 0, apres_id

    batch, items, total = [], [], 0
    for change in pending:
        item = {
            'model': change.model_label,
            'object_uuid': str(change.object_uuid) if change.object_uuid else None,
            'operation': change.operation,
            'payload': change.payload,
            # Permet au serveur de reconnaitre un renvoi du meme changement.
            'client_change_id': change.id,
        }
        size = len(json.dumps(item))
        if items and total + size > MAX_PUSH_BYTES:
            break  # le reste partira au cycle suivant
        items.append(item)
        batch.append(change)
        total += size

    curseur = batch[-1].id
    response = _request_json(
        f'{server}/api/v1/sync/push/', device_id, token, {'changes': items},
    )
    if not response.get('ok'):
        return 0, apres_id
    accepted = {item['index'] for item in response.get('accepted', [])}
    rejected = {
        item['index']: item.get('error', '')
        for item in response.get('rejected', []) if 'index' in item
    }
    now = timezone.now()
    updated = 0
    for index, change in enumerate(batch):
        if index in accepted:
            change.statut = SyncChange.STATUT_APPLIED
            change.date_application = now
            change.save(update_fields=['statut', 'date_application'])
            updated += 1
        elif index in rejected:
            # Reste PENDING donc renvoye plus tard : la dependance manquante
            # peut arriver entre-temps. Passe les tentatives epuisees, le refus
            # n'est plus temporaire -> on cesse d'insister et on trace.
            change.erreur = str(rejected[index])[:500]
            change.tentatives = (change.tentatives or 0) + 1
            if change.tentatives >= MAX_PUSH_ATTEMPTS:
                change.statut = SyncChange.STATUT_ABANDONED
                _log_abandon(change, 'envoi')
            change.save(update_fields=['statut', 'erreur', 'tentatives'])
    return updated, curseur


def _push_tout(server, device_id, token, ecole):
    """Vide la file d'envoi locale, lot apres lot, dans le meme cycle."""
    total, curseur = 0, 0
    for _ in range(MAX_LOTS_PAR_CYCLE):
        envoyes, prochain = _push(server, device_id, token, ecole, curseur)
        if prochain == curseur:
            # Plus rien a envoyer, ou le serveur a refuse le lot entier : dans
            # les deux cas insister maintenant ne changerait rien.
            break
        total += envoyes
        curseur = prochain
    return total


def _try_apply(change) -> bool:
    """Applique un changement recu ; enregistre l'echec pour le rejouer."""
    from .models import SyncChange
    from .engine import apply_sync_change
    try:
        apply_sync_change(change)
        return True
    except Exception as exc:
        change.erreur = str(exc)[:500]
        change.tentatives = (change.tentatives or 0) + 1
        if change.tentatives >= MAX_APPLY_ATTEMPTS:
            change.statut = SyncChange.STATUT_ABANDONED
            _log_abandon(change, 'reception')
        else:
            change.statut = SyncChange.STATUT_FAILED
        change.save(update_fields=['statut', 'erreur', 'tentatives'])
        return False


def _retry_failed(ecole) -> int:
    """
    Rejoue les changements recus qui n'ont pas pu etre appliques.

    Un echec est le plus souvent temporaire : l'objet lie (classe, eleve...)
    n'etait pas encore arrive. Comme `since_id` avance quoi qu'il arrive, sans
    cette reprise le changement ne serait jamais redemande et la donnee serait
    perdue definitivement.

    Seuls les changements RECUS passent par ce statut : un changement local
    refuse au push est marque ABANDONED, jamais FAILED, pour ne pas etre
    reapplique ici alors qu'il est deja en base.
    """
    from .models import SyncChange
    failed = list(
        SyncChange.objects
        .filter(ecole=ecole, statut=SyncChange.STATUT_FAILED)
        .order_by('id')[:200]
    )
    return sum(1 for change in failed if _try_apply(change))


def _apply_pull_response(response, ecole):
    """Applique un lot recu. Retourne (nombre_applique, nombre_recu)."""
    from .models import SyncChange
    if not response.get('ok'):
        return 0, 0
    recus = len(response.get('changes') or [])
    created = 0
    for item in response.get('changes', []):
        server_change_id = item.get('id')
        if server_change_id and SyncChange.objects.filter(
            ecole=ecole, payload__server_change_id=server_change_id,
        ).exists():
            continue
        payload = item.get('payload') or {}
        if server_change_id:
            payload = {**payload, 'server_change_id': server_change_id}
        change = SyncChange.objects.create(
            ecole=ecole,
            model_label=item['model_label'],
            object_uuid=item.get('object_uuid') or None,
            operation=item['operation'],
            payload=payload,
        )
        if _try_apply(change):
            created += 1
    _save_since_id(response.get('latest_change_id'))
    return created, recus


def _server_watermark(server, device_id, token):
    """
    Dernier changement connu du serveur, en une requete minuscule.

    C'est ce qui autorise une cadence de quelques secondes : tant que le
    repere n'a pas bouge, le poste n'a rien a demander et le serveur n'a rien
    a serialiser. Retourne None si le serveur ne connait pas encore cette
    route (version anterieure) : on retombe alors sur le pull complet.
    """
    try:
        response = _request_json(
            f'{server}/api/v1/sync/state/', device_id, token,
            payload=None, method='GET', timeout=20,
        )
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not response.get('ok'):
        return None
    valeur = response.get('last_change_id')
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _pull(server, device_id, token, ecole):
    """Recupere un lot. Retourne (nombre_applique, nombre_recu)."""
    since_id = _load_since_id()
    suffix = f'?since_id={since_id}' if since_id else ''
    response = _request_json(
        f'{server}/api/v1/sync/pull/{suffix}', device_id, token,
        payload=None, method='GET',
    )
    return _apply_pull_response(response, ecole)


def _since_local():
    """Repere local, en entier. 0 si le fichier d'etat est illisible."""
    try:
        return int(_load_since_id() or 0)
    except (TypeError, ValueError):
        # On redemande tout plutot que de risquer de sauter un changement.
        return 0


def _pull_if_needed(server, device_id, token, ecole):
    """
    Ne telecharge que si le serveur a effectivement du nouveau, puis vide
    entierement le retard accumule au lieu d'un seul lot.
    """
    local = _since_local()
    distant = _server_watermark(server, device_id, token)
    if distant is not None and distant <= local:
        return 0

    applique = 0
    for _ in range(MAX_LOTS_PAR_CYCLE):
        avant = _since_local()
        lot_applique, recus = _pull(server, device_id, token, ecole)
        applique += lot_applique
        apres = _since_local()
        if not recus or apres <= avant:
            # Lot vide, ou repere qui n'avance pas : continuer bouclerait sur
            # la meme requete sans jamais progresser.
            break
        if distant is not None and apres >= distant:
            # Le poste a rattrape le filigrane releve en debut de cycle. Ce qui
            # est arrive depuis sera servi au cycle suivant, dans la seconde.
            break
    return applique


def _bootstrap_school(server, device_id, token, configured_ecole_id):
    """Cree l'ecole locale depuis le snapshot d'un poste neuf.

    ``SyncChange`` possede une cle etrangere vers Ecole. Sur une installation
    vierge, il faut donc amorcer l'objet Ecole avant de pouvoir enregistrer et
    appliquer le reste du snapshot initial.
    """
    from uuid import UUID

    from django.db import models

    from eleves.models import Ecole
    from .context import mute_sync
    from .engine import SYNC_FIELD_NAMES, deserialize_field

    response = _request_json(
        f'{server}/api/v1/sync/pull/?initial=1', device_id, token,
        payload=None, method='GET', timeout=120,
    )
    if not response.get('ok'):
        logger.error(
            "[Sync] Le serveur a refuse l'instantane initial : %s",
            response.get('error') or response,
        )
        return None
    if str(response.get('ecole_id') or '') != str(configured_ecole_id):
        logger.error(
            "[Sync] L'ecole retournee par le serveur (%s) ne correspond pas "
            "a la configuration locale (%s).",
            response.get('ecole_id'), configured_ecole_id,
        )
        return None

    school_item = next((
        item for item in response.get('changes', [])
        if (item.get('model_label') or item.get('model')) == 'eleves.Ecole'
        and item.get('operation') != 'DELETE'
    ), None)
    if not school_item:
        logger.error("[Sync] Snapshot initial sans fiche ecole.")
        return None

    payload = school_item.get('payload') or {}
    raw_uuid = school_item.get('object_uuid') or payload.get('sync_uuid')
    if not raw_uuid:
        logger.error("[Sync] Snapshot initial sans UUID d'ecole.")
        return None

    try:
        local_pk = int(configured_ecole_id)
    except (TypeError, ValueError):
        local_pk = None

    # Une reinstallation ou une mise a jour peut restaurer une ancienne base
    # contenant deja l'ecole avec le meme identifiant local, mais sans fichier
    # d'etat de synchronisation. Il ne faut pas prendre cette simple presence
    # pour un bootstrap termine : on rattache cette fiche a l'UUID canonique du
    # serveur, puis on applique l'instantane complet.
    ecole = Ecole.objects.filter(sync_uuid=raw_uuid).first()
    if not ecole and local_pk:
        ecole = Ecole.objects.filter(pk=local_pk).first()
    if not ecole:
        ecole = Ecole(sync_uuid=UUID(str(raw_uuid)))
        if local_pk and not Ecole.objects.filter(pk=local_pk).exists():
            ecole.pk = local_pk
    else:
        ecole.sync_uuid = UUID(str(raw_uuid))

    for field in Ecole._meta.concrete_fields:
        if field.name == 'id' or field.name in SYNC_FIELD_NAMES:
            continue
        if field.name not in payload:
            continue
        value = deserialize_field(field, payload.get(field.name))
        if (
            value is None and not field.null and not field.blank
            and isinstance(field, (models.ForeignKey, models.OneToOneField))
        ):
            continue
        setattr(ecole, field.name, value)
    ecole.is_synced = True
    with mute_sync():
        ecole.save()

    _apply_pull_response(response, ecole)
    _save_state(initial_done=True, school_sync_uuid=ecole.sync_uuid)
    logger.info("[Sync] Initialisation locale terminee pour l'ecole %s.", ecole.pk)
    return ecole


def _local_school(configured_ecole_id):
    """Retrouve l'ecole locale canonique apres le bootstrap initial."""
    from eleves.models import Ecole

    state = _load_state()
    school_sync_uuid = state.get('school_sync_uuid')
    if school_sync_uuid:
        ecole = Ecole.objects.filter(sync_uuid=school_sync_uuid).first()
        if ecole:
            return ecole
    return Ecole.objects.filter(pk=configured_ecole_id).first()


def _signaler_echec(cause: str) -> None:
    """Trace un cycle de synchronisation en echec, sans noyer le journal."""
    global _echecs_consecutifs, _dernier_log_echec
    _echecs_consecutifs += 1
    maintenant = time.monotonic()
    premier_de_la_serie = _echecs_consecutifs == 1
    if premier_de_la_serie or (maintenant - _dernier_log_echec) >= INTERVALLE_LOG_ECHEC_SECONDES:
        logger.warning(
            "[Sync] Synchronisation en echec depuis %d tentative(s) "
            "(reseau, serveur injoignable, ou identifiants invalides) : %s",
            _echecs_consecutifs, cause,
        )
        _dernier_log_echec = maintenant


def _signaler_succes() -> None:
    """Trace le retour a la normale apres une serie d'echecs."""
    global _echecs_consecutifs
    if _echecs_consecutifs:
        logger.info(
            "[Sync] Synchronisation retablie apres %d tentative(s) en echec.",
            _echecs_consecutifs,
        )
        _echecs_consecutifs = 0


def _tenter_cycle() -> bool:
    """
    Une passe push + pull, sans filet : toute exception remonte a l'appelant.

    Separee de `_run_once` pour que `diagnostiquer_synchronisation()` puisse
    afficher l'exception brute a un humain, plutot que la version resumee et
    limitee en frequence que `_run_once` trace dans le journal.
    """
    cfg = _config()
    if not cfg:
        return False
    server, device_id, token, ecole_id = cfg

    state = _load_state()
    ecole = _local_school(ecole_id)
    # L'absence du marqueur est volontairement prioritaire sur la presence
    # d'une fiche Ecole : une base restauree peut contenir cette fiche sans
    # avoir jamais recu les classes, eleves et paiements du serveur.
    if not state.get('initial_done'):
        ecole = _bootstrap_school(server, device_id, token, ecole_id)
        if not ecole:
            # `_bootstrap_school` a deja trace la cause explicite (ecole
            # inconnue, snapshot vide...) quand elle en a une ; sinon l'appel
            # a echoue plus bas et remonte par l'exception a l'appelant.
            return False
        # Le snapshot vient d'etre applique. Le prochain cycle enverra les
        # eventuels changements locaux et passera en pull incremental.
        _retry_failed(ecole)
        _mark_transfer()
        return True

    echanges = _push_tout(server, device_id, token, ecole)
    echanges += _pull_if_needed(server, device_id, token, ecole)
    # Le lot qui vient d'arriver apporte peut-etre la dependance qui manquait
    # aux echecs precedents : on les rejoue tout de suite.
    echanges += _retry_failed(ecole)
    if echanges:
        _mark_transfer()
    return True


def _run_once() -> bool:
    """Une passe push + pull, protegee. Retourne True si le serveur a repondu."""
    try:
        resultat = _tenter_cycle()
    except (HTTPError, URLError, OSError) as exc:
        # Hors-ligne ou serveur injoignable -> reessai au prochain cycle. Trace
        # tout de meme : voir _signaler_echec.
        _signaler_echec(str(exc) or type(exc).__name__)
        return False
    except Exception as exc:
        _signaler_echec(f'{type(exc).__name__}: {exc}')
        return False
    if resultat:
        _signaler_succes()
    return resultat


def diagnostiquer_synchronisation() -> int:
    """
    Un cycle de synchronisation immediat, avec le detail complet d'un echec.

    A la difference du worker en arriere-plan, qui reessaie en silence et ne
    trace qu'un resume limite en frequence, cette fonction est faite pour etre
    declenchee a la main quand un poste semble ne pas synchroniser : elle
    donne tout de suite la meme information qu'exigerait, autrement, plusieurs
    minutes d'attente et une lecture du journal.

    Retourne un code de sortie (0 = succes, 1 = echec), pour un usage en ligne
    de commande.
    """
    cfg = _config()
    if not cfg:
        print("[Diagnostic] Configuration de synchronisation incomplete ou absente.")
        print("             Verifiez, dans sync_config.json : MYSCHOOL_SYNC_SERVER_URL,")
        print("             MYSCHOOL_SYNC_DEVICE_ID, MYSCHOOL_SYNC_TOKEN, "
              "MYSCHOOL_SYNC_ECOLE_ID.")
        return 1

    server, device_id, token, ecole_id = cfg
    etat = _load_state()
    print(f"[Diagnostic] Serveur    : {server}")
    print(f"[Diagnostic] Appareil   : {device_id}")
    print(f"[Diagnostic] Ecole      : {ecole_id}")
    print(
        "[Diagnostic] Etat local : "
        + ("deja initialise" if etat.get('initial_done')
           else "jamais initialise (le premier cycle va tenter l'instantane complet)")
    )
    print("[Diagnostic] Tentative de connexion au serveur...")

    debut = time.monotonic()
    try:
        reussi = _tenter_cycle()
    except Exception as exc:
        duree = time.monotonic() - debut
        print(f"[Diagnostic] ECHEC apres {duree:.1f} s : {type(exc).__name__}: {exc}")
        _suggerer_cause(exc)
        return 1
    duree = time.monotonic() - debut

    if reussi:
        print(f"[Diagnostic] SUCCES en {duree:.1f} s.")
        repere = _load_state().get('since_id') or '(aucun pour le moment)'
        print(f"[Diagnostic] Dernier changement connu localement : {repere}")
        return 0

    print(f"[Diagnostic] Echec en {duree:.1f} s, sans exception : l'ecole locale est "
          "introuvable, ou le serveur ne l'a pas reconnue. Voir les lignes ci-dessus.")
    return 1


def _suggerer_cause(exc: Exception) -> None:
    """
    Traduit une exception technique en cause probable, pour un lecteur non
    technicien face a un poste qui refuse de se synchroniser.
    """
    import ssl

    texte = str(exc)
    if isinstance(exc, ssl.SSLCertVerificationError) or 'CERTIFICATE_VERIFY_FAILED' in texte:
        print("[Diagnostic] Cause probable : le certificat HTTPS du serveur n'est pas")
        print("             reconnu par cette installation de MySchoolGN, alors que")
        print("             Windows lui fait confiance (un navigateur, lui, fonctionne).")
        print("             Frequent derriere un pare-feu ou un antivirus qui inspecte")
        print("             le trafic HTTPS avec son propre certificat.")
    elif isinstance(exc, HTTPError):
        if exc.code == 403:
            print("[Diagnostic] Cause probable : cet appareil ou son jeton ne sont plus")
            print("             valides cote serveur. Revoquez ce poste dans")
            print("             Administration > Version hors ligne, puis generez une")
            print("             nouvelle configuration.")
        else:
            print(f"[Diagnostic] Le serveur a repondu avec le code HTTP {exc.code}.")
    elif isinstance(exc, URLError):
        print("[Diagnostic] Cause probable : reseau, proxy ou pare-feu qui bloque les")
        print("             connexions sortantes de cette application specifiquement")
        print("             (un navigateur peut fonctionner sans que ce soit le cas ici).")
    elif 'no such table' in texte.lower():
        print("[Diagnostic] Cause probable : la base de donnees locale n'est pas encore")
        print("             initialisee. Lancez MySchoolGN.exe normalement une premiere")
        print("             fois (sans --diagnostiquer-sync), laissez-le migrer la base,")
        print("             puis relancez ce diagnostic.")


# ─── Worker ─────────────────────────────────────────────────────────────────
def _next_delay(ok: bool, fast_interval: int, interval: int) -> float:
    """
    Delai avant le prochain cycle.

    Hors-ligne : reessai rapproche, pour rattraper des le retour du reseau.
    Juste apres un echange : cadence rapide, l'utilisateur attend de voir la
    donnee apparaitre. Au repos : cadence lente, chaque verification restant
    de toute facon minuscule grace au repere de fraicheur.
    """
    if not ok:
        return max(5, min(fast_interval * 2, 15))
    return fast_interval if _is_hot() else interval


def _worker(interval: int, boot_delay: int, fast_interval: int):
    # `wait` plutot que `sleep` : une saisie faite pendant le demarrage
    # declenche immediatement le premier cycle.
    _wake.wait(max(0, boot_delay))
    while True:
        declenche_par_saisie = _wake.is_set()
        _wake.clear()
        if declenche_par_saisie:
            # Laisse le temps a l'operation en cours d'ecrire tous ses objets.
            time.sleep(DEBOUNCE_SECONDS)
            _wake.clear()
        try:
            if not _is_configured():
                # Poste non configure : la configuration est lue au demarrage,
                # elle ne changera pas en cours de route -> veille longue.
                time.sleep(max(300, interval * 10))
                continue
            ok = _run_once()
        except Exception:
            ok = False
        _wake.wait(_next_delay(ok, fast_interval, interval))


def cadence_effective(interval: int, fast_interval: int):
    """
    Cadences reellement appliquees, une fois les bornes posees.

    Les postes deja installes portent un `sync_config.json` ecrit quand
    l'intervalle valait 60 s, voire davantage. Le laisser tel quel les
    priverait du temps reel sans que personne ne s'en apercoive : au repos
    aussi, la verification se limite desormais a un repere minuscule, donc
    rien ne justifie d'attendre plus que ce plafond.

    Le calcul est expose pour que le message de demarrage annonce ce qui se
    passe vraiment. Il affichait la valeur du fichier de configuration, pas
    celle retenue : sur un poste regle a 60 s, il annoncait une lenteur qui
    n'existait plus, de quoi envoyer chercher un probleme ailleurs.
    """
    fast_interval = max(1, min(fast_interval, interval))
    interval = max(fast_interval, min(interval, MAX_IDLE_INTERVAL))
    return interval, fast_interval


def start(interval: int = 10, boot_delay: int = 8, fast_interval: int = 2) -> bool:
    """
    Demarre le worker de synchronisation automatique (idempotent).

    interval      : secondes entre deux verifications au repos.
    boot_delay    : delai initial avant la premiere tentative.
    fast_interval : cadence apres une saisie ou une reception, pour que les
                    donnees apparaissent tout de suite sur les autres postes.
    Retourne True si le thread vient d'etre demarre.
    """
    global _started
    with _lock:
        if _started:
            return False
        _started = True
    interval, fast_interval = cadence_effective(interval, fast_interval)
    thread = threading.Thread(
        target=_worker, args=(interval, boot_delay, fast_interval),
        name='auto-sync', daemon=True,
    )
    thread.start()
    return True
