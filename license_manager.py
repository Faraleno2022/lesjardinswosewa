"""
MySchoolGN - Système de Gestion des Licences
=============================================
Auteur  : GS Hadja Kanfing Dian
Version : 1.0.0

Ce module gère la validation des licences d'utilisation de MySchoolGN.
Les licences peuvent être liées à une machine ou distribuables (mid="*").
"""

import os
import sys
import uuid
import hmac
import hashlib
import json
import base64
import socket
import platform
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Compatibilité Python 3.11+
def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

# ─── Clé secrète (obfusquée — ne pas modifier) ───────────────────────────────
def _gk():
    _d = [29,9,119,18,27,30,16,27,119,17,27,20,28,19,20,29,119,30,19,27,20,119,23,3,9,25,18,21,21,22,119,29,20,119,104,106,104,110,119,9,31,25,8,31,14,119,17,31,3,119,44,107]
    return bytes(x ^ 0x5A for x in _d)
_DEV_SECRET = _gk()
del _gk

# ─── Chemin de stockage de la licence ─────────────────────────────────────────
def _get_license_path() -> Path:
    if getattr(sys, 'frozen', False):
        base = Path(sys.executable).parent
    else:
        base = Path(__file__).parent
    return base / 'license.dat'

def _get_appdata_license_path() -> Path:
    appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
    folder = Path(appdata) / 'MySchoolGN'
    folder.mkdir(parents=True, exist_ok=True)
    return folder / 'license.dat'

# ─── Identifiant machine ───────────────────────────────────────────────────────
def get_machine_id() -> str:
    """Génère un identifiant unique et stable pour cette machine."""
    parts = []

    # UUID Windows (registre)
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r'SOFTWARE\Microsoft\Cryptography')
        machine_guid, _ = winreg.QueryValueEx(key, 'MachineGuid')
        parts.append(machine_guid)
    except Exception:
        pass

    # Hostname
    try:
        parts.append(socket.gethostname())
    except Exception:
        pass

    # UUID du système
    try:
        parts.append(str(uuid.getnode()))
    except Exception:
        pass

    # Plateforme
    parts.append(platform.system() + platform.machine())

    combined = '|'.join(parts).encode('utf-8')
    return hashlib.sha256(combined).hexdigest()[:32].upper()


def get_machine_id_short() -> str:
    """Version courte de 8 caractères pour affichage."""
    return get_machine_id()[:8]


# ─── Empreintes machine autorisées pour la génération ─────────────────────────
# Chaque entrée = liste d'octets XORés avec 0x95 (obfuscation anti-`strings`).
# Pour ajouter une machine : récupérer son ID court (8 chars hex via
# `python license_manager.py info`), puis XORer chaque caractère avec 0x95.
def _ak():
    _entries = [
        [0xD4,0xD1,0xA5,0xD4,0xA3,0xA0,0xA0,0xA3],  # AD0A6556 (machine dev historique)
        [0xA7,0xD0,0xA6,0xD1,0xA7,0xA1,0xA2,0xA2],  # 2E3D2477 (machine dev actuelle)
    ]
    return tuple(bytes(x ^ 0x95 for x in entry).decode() for entry in _entries)
_AUTHORIZED_PREFIXES = _ak()
del _ak


def _is_authorized_machine() -> bool:
    """Vérifie que la machine courante est autorisée à générer des licences."""
    try:
        mid = get_machine_id()[:8]
        return any(hmac.compare_digest(mid, p) for p in _AUTHORIZED_PREFIXES)
    except Exception:
        return False


def _is_distributable_mid(machine_id: str) -> bool:
    """Retourne True pour une licence utilisable sur plusieurs machines."""
    return str(machine_id or '').strip().upper() in {'*', 'ANY', 'ALL', 'DISTRIBUTABLE'}


# ─── Génération de clé de licence ─────────────────────────────────────────────
def generate_license_key(machine_id: str, expiry_days: int = 365,
                          school_name: str = '', edition: str = 'Standard') -> str:
    """
    Génère une clé de licence pour une machine donnée.
    Réservé au développeur / outil d'activation.
    BLOQUÉ si la machine n'est pas autorisée.

    Format retourné : XXXX-XXXX-XXXX-XXXX-XXXX
    """
    if not _is_authorized_machine():
        raise PermissionError(
            "Génération de licence non autorisée sur cette machine.\n"
            "Seule la machine du développeur GS Hadja Kanfing Dian peut générer des licences."
        )
    payload = {
        'mid': machine_id,
        'exp': (_now_utc() + timedelta(days=expiry_days)).strftime('%Y%m%d'),
        'school': school_name[:40],
        'edition': edition,
    }
    payload_str = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.b64encode(payload_str.encode()).decode()

    # Signature HMAC-SHA256
    sig = hmac.new(_DEV_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest()[:16].upper()

    # Encoder le payload en blocs de 4 chars
    payload_hex = hashlib.md5(payload_b64.encode()).hexdigest().upper()
    blocks = [payload_hex[i:i+4] for i in range(0, 16, 4)]
    sig_blocks = [sig[i:i+4] for i in range(0, 16, 4)]

    # Stocker le payload complet encodé séparément
    full_key_data = base64.b64encode(
        json.dumps({'payload': payload_b64, 'sig': sig}).encode()
    ).decode()

    # Clé affichable = 5 groupes de 4 chars
    display_key = '-'.join(blocks + [sig_blocks[0]])
    return display_key, full_key_data


def generate_activation_file(machine_id: str, expiry_days: int = 365,
                               school_name: str = '', edition: str = 'Standard') -> dict:
    """
    Génère un fichier d'activation complet (à envoyer au client).
    BLOQUÉ si la machine n'est pas autorisée.
    """
    if not _is_authorized_machine():
        raise PermissionError(
            "Génération de licence non autorisée sur cette machine.\n"
            "Seule la machine du développeur GS Hadja Kanfing Dian peut générer des licences."
        )
    payload = {
        'mid': machine_id,
        'exp': (_now_utc() + timedelta(days=expiry_days)).strftime('%Y%m%d'),
        'school': school_name[:60],
        'edition': edition,
        'issued': _now_utc().strftime('%Y-%m-%d'),
        'issuer': 'GS Hadja Kanfing Dian',
    }
    payload_str = json.dumps(payload, separators=(',', ':'))
    payload_b64 = base64.b64encode(payload_str.encode()).decode()
    sig = hmac.new(_DEV_SECRET, payload_b64.encode(), hashlib.sha256).hexdigest().upper()

    return {
        'license_data': payload_b64,
        'signature': sig,
        'version': '1.0',
    }


def generate_distributable_activation_file(expiry_days: int = 365,
                                           school_name: str = '',
                                           edition: str = 'Standard') -> dict:
    """Génère une licence .lic non liée à une machine précise."""
    return generate_activation_file('*', expiry_days, school_name, edition)


# ─── Validation de licence ─────────────────────────────────────────────────────
def _validate_license_data(license_dict: dict) -> dict:
    """
    Valide un dictionnaire de licence.
    Retourne un dict avec 'valid', 'reason', 'payload'.
    """
    try:
        payload_b64 = license_dict.get('license_data', '')
        sig = license_dict.get('signature', '')
        version = license_dict.get('version', '1.0')

        if not payload_b64 or not sig:
            return {'valid': False, 'reason': 'Fichier de licence incomplet.'}

        # Vérifier la signature
        expected_sig = hmac.new(
            _DEV_SECRET, payload_b64.encode(), hashlib.sha256
        ).hexdigest().upper()

        if not hmac.compare_digest(sig.upper(), expected_sig):
            return {'valid': False, 'reason': 'Signature de licence invalide.'}

        # Décoder le payload
        payload = json.loads(base64.b64decode(payload_b64).decode())
        machine_id = get_machine_id()

        # Vérifier la machine sauf pour les licences distribuables.
        payload_mid = payload.get('mid', '')
        distributable = _is_distributable_mid(payload_mid)
        if not distributable and payload_mid[:16] != machine_id[:16]:
            return {'valid': False, 'reason': 'Cette licence appartient à une autre machine.'}

        # Vérifier l'expiration
        exp_str = payload.get('exp', '20000101')
        exp_date = datetime.strptime(exp_str, '%Y%m%d')
        now = _now_utc()
        days_left = (exp_date - now).days

        if days_left < 0:
            return {
                'valid': False,
                'reason': f"Licence expirée depuis {abs(days_left)} jour(s).",
                'payload': payload,
            }

        return {
            'valid': True,
            'reason': 'Licence valide.',
            'payload': payload,
            'days_left': days_left,
            'school': payload.get('school', ''),
            'edition': payload.get('edition', 'Standard'),
            'distributable': distributable,
        }

    except Exception as e:
        return {'valid': False, 'reason': f'Erreur lors de la validation : {e}'}


def load_and_validate_license() -> dict:
    """
    Charge et valide la licence depuis les emplacements connus.
    Retourne un dict avec 'valid', 'reason', etc.
    """
    license_paths = [
        _get_license_path(),
        _get_appdata_license_path(),
    ]

    for path in license_paths:
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    license_dict = json.load(f)
                result = _validate_license_data(license_dict)
                result['license_path'] = str(path)
                return result
            except Exception:
                continue

    return {
        'valid': False,
        'reason': 'Aucune licence trouvée. Veuillez activer votre copie.',
    }


def save_license(license_dict: dict) -> bool:
    """Sauvegarde la licence dans tous les emplacements standards (redondance)."""
    saved = False
    for path in [_get_license_path(), _get_appdata_license_path()]:
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(license_dict, f, indent=2)
            saved = True
        except Exception:
            continue
    return saved


def activate_from_file(activation_file_path: str) -> dict:
    """
    Active la licence depuis un fichier .lic fourni par le développeur.
    """
    try:
        with open(activation_file_path, 'r', encoding='utf-8') as f:
            license_dict = json.load(f)
        result = _validate_license_data(license_dict)
        if result['valid']:
            if save_license(license_dict):
                return {**result, 'message': 'Licence activée avec succès !'}
            else:
                return {'valid': False, 'reason': 'Impossible de sauvegarder la licence.'}
        return result
    except Exception as e:
        return {'valid': False, 'reason': f'Erreur lecture du fichier : {e}'}


# ─── Vérification en ligne (API serveur de licences) ─────────────────────────
# Le serveur de licences signe un JWT HMAC-SHA256 que cette app vérifie
# localement (offline-friendly). Tant que le JWT n'est pas expiré (30 j max
# = grace period), l'app continue de fonctionner même sans réseau.
#
# Le secret HMAC est _DEV_SECRET (le même obfusqué plus haut). Il DOIT être
# identique côté serveur (LICENCE_HMAC_SECRET dans licence_server/settings.py).

import urllib.request
import urllib.error

# URL de base — surchargeable via variable d'environnement pour les tests
_LICENCE_API_BASE = os.environ.get(
    'LICENCE_API_BASE',
    'https://www.myschoolgn.space/api/v1/license',
)
_API_TIMEOUT_SEC = 5
_CHECK_INTERVAL_HOURS = 6   # idem côté serveur


def _b64url_decode(s: str) -> bytes:
    pad = '=' * ((4 - len(s) % 4) % 4)
    return base64.urlsafe_b64decode((s + pad).encode('ascii'))


def _verify_jwt_offline(token: str) -> dict:
    """
    Vérifie la signature HMAC-SHA256 d'un JWT et son expiration.
    Retourne le payload décodé. Lève ValueError si invalide.
    """
    try:
        header_b64, payload_b64, sig_b64 = token.split('.')
    except ValueError:
        raise ValueError("Token JWT mal formé.")

    signing_input = f"{header_b64}.{payload_b64}".encode('ascii')
    expected_sig = hmac.new(_DEV_SECRET, signing_input, hashlib.sha256).digest()
    actual_sig = _b64url_decode(sig_b64)

    if not hmac.compare_digest(expected_sig, actual_sig):
        raise ValueError("Signature JWT invalide.")

    payload = json.loads(_b64url_decode(payload_b64).decode('utf-8'))

    # Vérifier exp
    now_ts = int(_now_utc().timestamp())
    if 'exp' in payload and payload['exp'] < now_ts:
        raise ValueError("Token JWT expiré (grace period écoulée).")

    return payload


def _call_api(endpoint: str, body: dict) -> dict | None:
    """
    POST JSON vers l'API serveur. Retourne {status_code, body_dict} ou None
    si réseau indisponible.
    """
    url = f"{_LICENCE_API_BASE}/{endpoint}"
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(
        url, data=data, method='POST',
        headers={
            'Content-Type': 'application/json',
            'User-Agent': f'MySchoolGN/{platform.system()} python-urllib',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_API_TIMEOUT_SEC) as resp:
            body_str = resp.read().decode('utf-8')
            return {'status_code': resp.status, 'body': json.loads(body_str)}
    except urllib.error.HTTPError as e:
        # 4xx → on a quand même un JSON exploitable
        try:
            body_str = e.read().decode('utf-8')
            return {'status_code': e.code, 'body': json.loads(body_str)}
        except Exception:
            return {'status_code': e.code, 'body': {'status': 'invalid',
                                                    'reason': f'HTTP {e.code}'}}
    except (urllib.error.URLError, TimeoutError, OSError):
        return None  # réseau indisponible


def activate_online(license_key: str) -> dict:
    """
    1re activation : envoie la clé + machine_id au serveur, reçoit un JWT
    signé et le sauvegarde dans license.dat.
    """
    key = license_key.strip().upper()
    mid = get_machine_id()
    try:
        hostname = socket.gethostname()
    except Exception:
        hostname = ''

    resp = _call_api('activate', {
        'license_key': key,
        'machine_id': mid,
        'hostname': hostname,
    })

    if resp is None:
        return {'valid': False,
                'reason': 'Serveur de licences injoignable. Vérifiez votre connexion internet.'}

    body = resp['body']
    if resp['status_code'] != 200:
        return {'valid': False,
                'reason': body.get('reason', f"Erreur HTTP {resp['status_code']}"),
                'status': body.get('status', 'invalid')}

    # Sauvegarder le token + métadonnées
    license_dict = {
        'version':        '2.0',
        'license_key':    key,
        'machine_id':     mid,
        'signed_token':   body['signed_token'],
        'school':         body.get('school', ''),
        'edition':        body.get('edition', 'Standard'),
        'deploiement':    body.get('deploiement', 'local'),
        'expires_at':     body.get('expires_at'),
        'last_check_at':  _now_utc().isoformat() + 'Z',
    }
    if not save_license(license_dict):
        return {'valid': False, 'reason': 'Impossible de sauvegarder la licence localement.'}

    return {
        'valid':      True,
        'message':    'Licence activée avec succès !',
        'school':     body.get('school', ''),
        'edition':    body.get('edition', 'Standard'),
        'days_left':  body.get('days_left', 0),
        'expires_at': body.get('expires_at'),
    }


def _load_local_token_status() -> dict | None:
    """
    Lit license.dat v2.0 et valide le JWT hors-ligne.
    Retourne un dict {valid, payload, license_key, last_check_at} ou None.
    """
    for path in (_get_license_path(), _get_appdata_license_path()):
        if not path.exists():
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        if data.get('version') != '2.0' or not data.get('signed_token'):
            continue  # ancien format, traité ailleurs
        try:
            payload = _verify_jwt_offline(data['signed_token'])
        except ValueError:
            continue
        # Vérifier que le token correspond à CETTE machine
        if payload.get('machine_id', '').upper() != get_machine_id().upper():
            continue
        last_check = data.get('last_check_at')
        try:
            last_check_dt = datetime.fromisoformat(last_check.rstrip('Z'))
        except Exception:
            last_check_dt = _now_utc() - timedelta(days=999)
        return {
            'valid': True,
            'payload': payload,
            'license_key': data.get('license_key', ''),
            'last_check_at': last_check_dt,
            'local_data': data,
            'license_path': str(path),
        }
    return None


def _update_local_check_timestamp(local_data: dict, new_body: dict | None = None):
    """Met à jour last_check_at (et le token si new_body fourni)."""
    local_data['last_check_at'] = _now_utc().isoformat() + 'Z'
    if new_body:
        local_data['signed_token'] = new_body.get('signed_token', local_data['signed_token'])
        local_data['expires_at']   = new_body.get('expires_at', local_data.get('expires_at'))
        local_data['school']       = new_body.get('school', local_data.get('school'))
        local_data['edition']      = new_body.get('edition', local_data.get('edition'))
    save_license(local_data)


def verify_online() -> dict | None:
    """
    Vérification périodique. Retourne un dict {valid, ...} ou None si
    aucune licence locale (→ fallback essai/legacy).
    """
    local = _load_local_token_status()
    if not local:
        return None

    payload = local['payload']
    age_hours = (_now_utc() - local['last_check_at']).total_seconds() / 3600

    # Cache frais → pas d'appel réseau
    if age_hours < _CHECK_INTERVAL_HOURS:
        return _status_from_payload(payload, source='cache')

    # Tenter une vérification fraîche
    resp = _call_api('verify', {
        'license_key': local['license_key'],
        'machine_id':  get_machine_id(),
    })

    if resp is None:
        # Réseau KO → on tolère tant que le JWT n'est pas expiré (déjà vérifié dans _verify_jwt_offline)
        return _status_from_payload(payload, source='offline_grace')

    if resp['status_code'] == 200:
        _update_local_check_timestamp(local['local_data'], resp['body'])
        return _status_from_payload_dict(resp['body'], source='online')

    # 4xx → licence pas OK selon le serveur (suspendue/expirée/révoquée…)
    body = resp['body']
    return {
        'valid': False,
        'reason': body.get('reason', 'Licence refusée par le serveur.'),
        'status': body.get('status', 'invalid'),
        'source': 'online_refused',
    }


def _status_from_payload(payload: dict, source: str) -> dict:
    """Construit un statut à partir d'un payload JWT décodé."""
    try:
        exp_date = datetime.strptime(payload['expires_at'], '%Y-%m-%d')
        days_left = max(0, (exp_date - _now_utc()).days)
    except Exception:
        days_left = 0
    return {
        'valid':      payload.get('status') == 'active' and days_left > 0,
        'trial':      False,
        'school':     payload.get('school', ''),
        'edition':    payload.get('edition', 'Standard'),
        'days_left':  days_left,
        'reason':     f"Licence active (vérif: {source}).",
        'source':     source,
    }


def _status_from_payload_dict(body: dict, source: str) -> dict:
    """Idem mais à partir de la réponse JSON brute de l'API."""
    return {
        'valid':      body.get('status') == 'active',
        'trial':      False,
        'school':     body.get('school', ''),
        'edition':    body.get('edition', 'Standard'),
        'days_left':  body.get('days_left', 0),
        'reason':     f"Licence active (vérif: {source}).",
        'source':     source,
    }


# ─── Mode démo (30 jours sans licence) ────────────────────────────────────────
_TRIAL_FILE_NAME = '.trial_start'

# Ancre d'essai dans le registre HKCU : survit à la désinstallation ET à la
# suppression manuelle du dossier d'installation / de %APPDATA%. Clé neutre
# volontairement distincte de celle supprimée par l'installateur.
_TRIAL_REG_SUBKEY = r'Software\MSGNRuntime'
_TRIAL_REG_VALUE = 'tk'


def _read_trial_registry(current_mid: str):
    """Lit la date d'essai depuis HKCU (retourne un datetime ou None)."""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_SUBKEY)
        try:
            val, _ = winreg.QueryValueEx(key, _TRIAL_REG_VALUE)
        finally:
            winreg.CloseKey(key)
        content = str(val).strip()
        if '|' in content:
            stored_mid, date_str = content.split('|', 1)
            if stored_mid == current_mid:
                return datetime.strptime(date_str, '%Y-%m-%d')
    except Exception:
        pass
    return None


def _write_trial_registry(current_mid: str, trial_start) -> None:
    """Écrit/ancre la date d'essai dans HKCU (silencieux en cas d'échec)."""
    try:
        import winreg
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, _TRIAL_REG_SUBKEY)
        try:
            winreg.SetValueEx(
                key, _TRIAL_REG_VALUE, 0, winreg.REG_SZ,
                f"{current_mid}|{trial_start.strftime('%Y-%m-%d')}",
            )
        finally:
            winreg.CloseKey(key)
    except Exception:
        pass


def get_or_create_trial() -> dict:
    """
    Gère une période d'essai de 30 jours sans licence.

    L'essai est lié à la machine (machine_id) et ancré dans PLUSIEURS
    emplacements persistants : dossier d'installation, %APPDATA% et registre
    HKCU. Ainsi une désinstallation/réinstallation — ou même la suppression
    manuelle du dossier d'installation — ne réinitialise PAS l'essai : la date
    la plus ancienne retrouvée fait foi et est resynchronisée partout.
    Format : machine_id_16|YYYY-MM-DD
    """
    trial_paths = [
        _get_license_path().parent / _TRIAL_FILE_NAME,
        _get_appdata_license_path().parent / _TRIAL_FILE_NAME,
    ]

    current_mid = get_machine_id()[:16]

    # 1) Rassembler toutes les ancres valides pour CETTE machine.
    #    On garde la date la PLUS ANCIENNE : supprimer une seule ancre ne
    #    permet pas de "rajeunir" l'essai tant qu'une autre subsiste.
    found_dates = []
    for tp in trial_paths:
        try:
            if tp.exists():
                with open(tp, 'r') as f:
                    content = f.read().strip()
                if '|' in content:
                    stored_mid, date_str = content.split('|', 1)
                    if stored_mid == current_mid:
                        found_dates.append(datetime.strptime(date_str, '%Y-%m-%d'))
                    # Machine différente → ignorer (copie USB)
                else:
                    # Ancien format (date seule) → accepter et migrer
                    found_dates.append(datetime.strptime(content, '%Y-%m-%d'))
        except Exception:
            continue

    reg_date = _read_trial_registry(current_mid)
    if reg_date is not None:
        found_dates.append(reg_date)

    trial_started = False
    if found_dates:
        trial_start = min(found_dates)
    else:
        # Aucune ancre nulle part → première installation réelle
        trial_start = _now_utc()
        trial_started = True

    # 2) Réécrire l'ancre dans TOUS les emplacements (pas de break) pour
    #    resynchroniser ceux qui auraient été effacés.
    stamp = f"{current_mid}|{trial_start.strftime('%Y-%m-%d')}"
    trial_path_used = None
    for tp in trial_paths:
        try:
            tp.parent.mkdir(parents=True, exist_ok=True)
            with open(tp, 'w') as f:
                f.write(stamp)
            if trial_path_used is None:
                trial_path_used = tp
        except Exception:
            continue
    _write_trial_registry(current_mid, trial_start)

    days_elapsed = (_now_utc() - trial_start).days
    days_left = max(0, 30 - days_elapsed)

    return {
        'trial': True,
        'valid': days_left > 0,
        'days_left': days_left,
        'days_elapsed': days_elapsed,
        'trial_started': trial_started,
        'trial_path': str(trial_path_used) if trial_path_used else '',
        'reason': (
            f"Mode essai : {days_left} jour(s) restant(s)."
            if days_left > 0
            else "Période d'essai expirée. Veuillez acheter une licence."
        ),
    }


# ─── Point d'entrée principal ──────────────────────────────────────────────────
def check_license_or_trial() -> dict:
    """
    Stratégie de vérification :
      1. Licence en ligne v2.0 (JWT signé, cache 6 h, grace offline 30 j)
      2. Licence locale v1.0 (ancien fichier .lic envoyé par mail)
      3. Mode essai gratuit 30 jours
    """
    # 1. Nouvelle licence en ligne
    online = verify_online()
    if online is not None:
        return online

    # 2. Ancien format local (compat)
    legacy = load_and_validate_license()
    if legacy['valid']:
        return legacy

    # 3. Mode essai
    return get_or_create_trial()


def print_license_status():
    """Affiche le statut de la licence dans la console."""
    mid = get_machine_id()
    mid_short = get_machine_id_short()
    status = check_license_or_trial()

    print("")
    print("=" * 60)
    print("   MySchoolGN — Statut de la Licence")
    print("=" * 60)
    print(f"   ID Machine  : {mid_short}...  (complet : {mid})")

    if status.get('trial'):
        print(f"   Mode        : ESSAI GRATUIT")
        print(f"   Jours rest. : {status['days_left']} / 30")
        print(f"   État        : {'Actif' if status['valid'] else 'EXPIRÉ'}")
        print("")
        print("   Pour obtenir une licence complète :")
        print("   → Contactez GS Hadja Kanfing Dian")
        print(f"   → Fournissez cet ID Machine : {mid}")
    else:
        valid = status['valid']
        print(f"   État        : {'VALIDE ✓' if valid else 'INVALIDE ✗'}")
        if valid:
            print(f"   École       : {status.get('school', 'N/A')}")
            print(f"   Édition     : {status.get('edition', 'Standard')}")
            print(f"   Expiration  : dans {status.get('days_left', 0)} jour(s)")
        else:
            print(f"   Raison      : {status.get('reason', 'Inconnue')}")

    print("=" * 60)
    print("")
    return status


# ─── Outil de génération de licence (usage développeur uniquement) ─────────────
if __name__ == '__main__':
    import sys
    # Forcer UTF-8 pour la console Windows
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    print("\nMySchoolGN - Gestionnaire de Licences")
    print("Auteur : GS Hadja Kanfing Dian")
    print("="*50)

    if len(sys.argv) < 2:
        print("\nUsages :")
        print("  python license_manager.py info")
        print("  python license_manager.py generate <machine_id> <jours> <ecole> <edition>")
        print("  python license_manager.py generate-distributable <jours> <ecole> <edition>")
        print("  python license_manager.py activate <fichier.lic>")
        print("  python license_manager.py activate-online <CLE-LICENCE>")
        print("  python license_manager.py check")
        print("  python license_manager.py encode <prefix8>")
        print("")
        print(f"  Serveur de licences : {_LICENCE_API_BASE}")
        print("  (Surchargeable via la variable d'environnement LICENCE_API_BASE)")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == 'info':
        mid = get_machine_id()
        print(f"\nID Machine complet : {mid}")
        print(f"ID Machine court   : {get_machine_id_short()}")
        print(f"\nFournissez l'ID complet à GS Hadja Kanfing Dian pour obtenir une licence.")

    elif cmd == 'generate':
        if len(sys.argv) < 4:
            print("Usage: python license_manager.py generate <machine_id> <jours> [ecole] [edition]")
            sys.exit(1)
        machine_id = sys.argv[2]
        days = int(sys.argv[3])
        school = sys.argv[4] if len(sys.argv) > 4 else ''
        edition = sys.argv[5] if len(sys.argv) > 5 else 'Standard'

        lic_data = generate_activation_file(machine_id, days, school, edition)
        output_file = f'license_{machine_id[:8]}.lic'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(lic_data, f, indent=2)
        print(f"\nLicence générée : {output_file}")
        print(f"  Machine  : {machine_id}")
        print(f"  École    : {school}")
        print(f"  Édition  : {edition}")
        print(f"  Durée    : {days} jours")
        print(f"\nEnvoyez le fichier '{output_file}' au client.")

    elif cmd == 'generate-distributable':
        if len(sys.argv) < 3:
            print("Usage: python license_manager.py generate-distributable <jours> [ecole] [edition]")
            sys.exit(1)
        days = int(sys.argv[2])
        school = sys.argv[3] if len(sys.argv) > 3 else ''
        edition = sys.argv[4] if len(sys.argv) > 4 else 'Standard'

        lic_data = generate_distributable_activation_file(days, school, edition)
        output_file = 'license_DISTRIBUTABLE.lic'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(lic_data, f, indent=2)
        print(f"\nLicence distribuable générée : {output_file}")
        print("  Machine  : toutes les machines")
        print(f"  École    : {school}")
        print(f"  Édition  : {edition}")
        print(f"  Durée    : {days} jours")
        print(f"\nEnvoyez le fichier '{output_file}' aux clients.")

    elif cmd == 'activate':
        if len(sys.argv) < 3:
            print("Usage: python license_manager.py activate <fichier.lic>")
            sys.exit(1)
        result = activate_from_file(sys.argv[2])
        if result['valid']:
            print(f"\n✓ {result.get('message', 'Activée')}")
            print(f"  École   : {result.get('school', 'N/A')}")
            print(f"  Édition : {result.get('edition', 'Standard')}")
            print(f"  Expire  : dans {result.get('days_left', 0)} jour(s)")
        else:
            print(f"\n✗ Échec : {result['reason']}")
            sys.exit(1)

    elif cmd == 'activate-online':
        if len(sys.argv) < 3:
            print("Usage: python license_manager.py activate-online <CLE-LICENCE>")
            print("       Ex: ABCD-1234-EFGH-5678-IJKL")
            sys.exit(1)
        key = sys.argv[2]
        print(f"\nActivation en ligne via : {_LICENCE_API_BASE}")
        print(f"Clé    : {key}")
        print(f"Machine: {get_machine_id()}")
        print("...")
        result = activate_online(key)
        if result['valid']:
            print(f"\n✓ {result['message']}")
            print(f"  École      : {result.get('school', 'N/A')}")
            print(f"  Édition    : {result.get('edition', 'Standard')}")
            print(f"  Expire le  : {result.get('expires_at', 'N/A')}")
            print(f"  Reste      : {result.get('days_left', 0)} jour(s)")
        else:
            print(f"\n✗ Échec activation : {result['reason']}")
            sys.exit(1)

    elif cmd == 'check':
        print_license_status()

    elif cmd == 'encode':
        if len(sys.argv) < 3:
            print("Usage: python license_manager.py encode <prefix8>")
            print("  prefix8 = 8 premiers caractères hex de l'ID machine (ex: 2E3D2477)")
            sys.exit(1)
        prefix = sys.argv[2].strip().upper()
        if len(prefix) != 8 or any(c not in '0123456789ABCDEF' for c in prefix):
            print(f"\n✗ Préfixe invalide : '{prefix}'")
            print("  Doit faire exactement 8 caractères hexadécimaux (0-9, A-F).")
            sys.exit(1)
        encoded = [ord(c) ^ 0x95 for c in prefix]
        line = '[' + ','.join(f'0x{b:02X}' for b in encoded) + ']'
        print(f"\nPréfixe        : {prefix}")
        print(f"Ligne à coller : {line},  # {prefix}")
        print(f"\nÀ ajouter dans `_entries` (fonction _ak), vers la ligne 91 de license_manager.py.")
