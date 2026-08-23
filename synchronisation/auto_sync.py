"""
Synchronisation automatique en arriere-plan (application Desktop).

Un thread daemon envoie (push) periodiquement les changements locaux en attente
puis recupere (pull) ceux des autres postes, via le serveur EN LIGNE configure.
Hors-ligne, chaque tentative echoue silencieusement et est reessayee a cadence
rapprochee : des que la connexion revient, la synchronisation se fait
automatiquement, sans action de l'utilisateur.

La logique push/pull est appelee DIRECTEMENT (et non via `call_command`) afin
de rester fiable dans l'executable PyInstaller, ou la decouverte des commandes
de management n'est pas garantie.

Configuration par machine (aucune recompilation) : fichier `sync_config.json`
charge par run_server.py -> reglages MYSCHOOL_SYNC_SERVER_URL / _ECOLE_ID /
_DEVICE_ID / _TOKEN. Voir `sync_config.example.json`.
"""
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

# Les payloads embarquent le contenu des fichiers : on borne le lot pousse par
# sa taille pour rester sous DATA_UPLOAD_MAX_MEMORY_SIZE (5 Mo) cote serveur.
MAX_PUSH_BYTES = 3 * 1024 * 1024

# Nombre d'echecs tolerees avant d'abandonner un changement : au-dela, la
# cause n'est plus temporaire. Sans cette borne, un changement irrecuperable
# est rejoue (ou repousse) a chaque cycle, indefiniment.
MAX_APPLY_ATTEMPTS = 5
MAX_PUSH_ATTEMPTS = 5


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


def _save_state(*, since_id=None, initial_done=None) -> None:
    state = _load_state()
    if since_id:
        state['since_id'] = since_id
    if initial_done is not None:
        state['initial_done'] = bool(initial_done)
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
            'X-Sync-Device': device_id,
            'X-Sync-Token': token,
        },
        method=method,
    )
    with urlrequest.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode('utf-8'))


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


def _push(server, device_id, token, ecole):
    from django.utils import timezone
    from .models import SyncChange
    pending = list(
        SyncChange.objects
        .filter(
            ecole=ecole,
            statut=SyncChange.STATUT_PENDING,
            tentatives__lt=MAX_PUSH_ATTEMPTS,
        )
        .order_by('id')[:200]
    )
    if not pending:
        return 0

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

    response = _request_json(
        f'{server}/api/v1/sync/push/', device_id, token, {'changes': items},
    )
    if not response.get('ok'):
        return 0
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
    return updated


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
    from .models import SyncChange
    if not response.get('ok'):
        return 0
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
    return created


def _pull(server, device_id, token, ecole):
    since_id = _load_since_id()
    suffix = f'?since_id={since_id}' if since_id else ''
    response = _request_json(
        f'{server}/api/v1/sync/pull/{suffix}', device_id, token,
        payload=None, method='GET',
    )
    return _apply_pull_response(response, ecole)


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

    existing = Ecole.objects.filter(sync_uuid=raw_uuid).first()
    if existing:
        ecole = existing
    else:
        ecole = Ecole(sync_uuid=UUID(str(raw_uuid)))
        try:
            local_pk = int(configured_ecole_id)
        except (TypeError, ValueError):
            local_pk = None
        if local_pk and not Ecole.objects.filter(pk=local_pk).exists():
            ecole.pk = local_pk

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
    _save_state(initial_done=True)
    logger.info("[Sync] Initialisation locale terminee pour l'ecole %s.", ecole.pk)
    return ecole


def _run_once() -> bool:
    """Une passe push + pull. Retourne True si le serveur a repondu."""
    cfg = _config()
    if not cfg:
        return False
    server, device_id, token, ecole_id = cfg
    try:
        from eleves.models import Ecole
        ecole = Ecole.objects.filter(pk=ecole_id).first()
        if not ecole:
            ecole = _bootstrap_school(server, device_id, token, ecole_id)
            if not ecole:
                return False
            # Le snapshot vient d'etre applique. Le prochain cycle enverra les
            # eventuels changements locaux et passera en pull incremental.
            _retry_failed(ecole)
            return True
        _push(server, device_id, token, ecole)
        _pull(server, device_id, token, ecole)
        # Le lot qui vient d'arriver apporte peut-etre la dependance qui
        # manquait aux echecs precedents : on les rejoue tout de suite.
        _retry_failed(ecole)
        return True
    except (HTTPError, URLError, OSError):
        # Hors-ligne ou serveur injoignable -> reessai au prochain cycle.
        return False
    except Exception:
        return False


# ─── Worker ───────────────────────────────────────────────────────────────────
def _worker(interval: int, boot_delay: int):
    time.sleep(max(0, boot_delay))  # laisser Django + le serveur demarrer
    fast = max(10, min(interval, 20))  # reessai rapproche quand hors-ligne
    while True:
        try:
            if not _is_configured():
                time.sleep(interval * 10)  # poste non configure -> veille longue
                continue
            ok = _run_once()
        except Exception:
            ok = False
        # En ligne : cadence normale. Hors-ligne : reessai rapide pour
        # rattraper des que la connexion revient.
        time.sleep(interval if ok else fast)


def start(interval: int = 60, boot_delay: int = 20) -> bool:
    """
    Demarre le worker de synchronisation automatique (idempotent).

    interval    : secondes entre deux synchros lorsque le serveur repond.
    boot_delay  : delai initial avant la premiere tentative.
    Retourne True si le thread vient d'etre demarre.
    """
    global _started
    with _lock:
        if _started:
            return False
        _started = True
    thread = threading.Thread(
        target=_worker, args=(interval, boot_delay),
        name='auto-sync', daemon=True,
    )
    thread.start()
    return True
