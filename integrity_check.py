"""
MySchoolGN — Système de vérification d'intégrité
==================================================
Protège l'application contre la modification non autorisée des fichiers.
Génère un manifeste de hachages au build, vérifie à l'exécution.

Utilisation :
  - Au build  : python integrity_check.py --generate
  - Au runtime: import integrity_check; integrity_check.verify()
"""

import os
import sys
import json
import hmac
import hashlib
from pathlib import Path

# ─── Clé de signature du manifeste (obfusquée) ──────────────────────────────
def _ik():
    _d = [52, 30, 7, 42, 61, 18, 33, 55, 8, 46, 29, 63, 11, 37, 50, 3,
          58, 21, 44, 15, 60, 26, 9, 48, 35, 2, 57, 19, 41, 13, 54, 31]
    return bytes((x ^ 0xA3) for x in _d)
_INTEGRITY_KEY = _ik()
del _ik

# ─── Répertoire de base ──────────────────────────────────────────────────────
def _base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent

# ─── Fichiers critiques à protéger ───────────────────────────────────────────
# NOTE ANTI-MODIFICATION : Les modules Python critiques (license_manager.py,
# integrity_check.py, load_env.py, run_server.py) sont compilés en bytecode
# dans le PYZ et ne sont PAS présents comme fichiers .py lisibles.
# La protection des modules compilés est assurée par le système de garde (.guard.dat).
CRITICAL_PATTERNS = [
    '.guard.dat',
]

# Fichiers de configuration Django (présents comme données si copiés)
DJANGO_PATTERNS = [
    'ecole_moderne/settings.py',
    'ecole_moderne/licence_middleware.py',
    'ecole_moderne/urls.py',
    'ecole_moderne/__init__.py',
]

# L'exécutable principal (vérification anti-tamper)
EXE_PATTERNS = [
    'MySchoolGN.exe',
]

# Fichiers .pyd (modules compilés Nuitka)
PYD_PATTERNS = [
    'license_manager.cp*.pyd',
]

MANIFEST_FILE = '.integrity.dat'


def _hash_file(filepath: Path) -> str:
    """Calcule le HMAC-SHA256 d'un fichier."""
    h = hmac.new(_INTEGRITY_KEY, b'', hashlib.sha256)
    try:
        with open(filepath, 'rb') as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
    except (OSError, IOError):
        return ''
    return h.hexdigest()


def _find_critical_files(base: Path) -> list:
    """Trouve tous les fichiers critiques."""
    files = []
    # Fichiers critiques principaux
    for pattern in CRITICAL_PATTERNS:
        p = base / pattern
        if p.exists():
            files.append(p)
        # En mode frozen ou si _internal/ existe, chercher aussi dedans
        p2 = base / '_internal' / pattern
        if p2.exists():
            files.append(p2)

    # Fichiers Django (s'ils existent sur disque)
    for pattern in DJANGO_PATTERNS:
        p = base / pattern
        if p.exists():
            files.append(p)
        p2 = base / '_internal' / pattern
        if p2.exists():
            files.append(p2)

    # Fichiers .pyd
    import glob
    for pattern in PYD_PATTERNS:
        for match in glob.glob(str(base / pattern)):
            files.append(Path(match))
        for match in glob.glob(str(base / '_internal' / pattern)):
            files.append(Path(match))

    # Exécutable principal
    for pattern in EXE_PATTERNS:
        p = base / pattern
        if p.exists():
            files.append(p)

    return files


def generate_manifest():
    """Génère le manifeste d'intégrité (à exécuter au moment du build)."""
    base = _base_dir()
    files = _find_critical_files(base)

    manifest = {}
    for f in files:
        rel = str(f.relative_to(base)).replace('\\', '/')
        h = _hash_file(f)
        if h:
            manifest[rel] = h

    # Signer le manifeste lui-même
    manifest_str = json.dumps(manifest, sort_keys=True, separators=(',', ':'))
    manifest_sig = hmac.new(
        _INTEGRITY_KEY, manifest_str.encode(), hashlib.sha256
    ).hexdigest()

    data = {
        'files': manifest,
        'sig': manifest_sig,
        'v': '1.0',
    }

    manifest_path = base / MANIFEST_FILE
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f)

    print(f"[Intégrité] Manifeste généré : {len(manifest)} fichiers protégés")
    for rel in sorted(manifest.keys()):
        print(f"  ✓ {rel}")
    return manifest_path


def verify() -> dict:
    """
    Vérifie l'intégrité des fichiers critiques.
    Retourne {'valid': bool, 'reason': str, 'tampered': list}
    """
    base = _base_dir()
    manifest_path = base / MANIFEST_FILE

    if not manifest_path.exists():
        # Pas de manifeste = mode développement, on laisse passer
        return {'valid': True, 'reason': 'dev_mode', 'tampered': []}

    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return {'valid': False, 'reason': 'Manifeste corrompu.', 'tampered': []}

    files_manifest = data.get('files', {})
    sig = data.get('sig', '')

    # Vérifier la signature du manifeste
    manifest_str = json.dumps(files_manifest, sort_keys=True, separators=(',', ':'))
    expected_sig = hmac.new(
        _INTEGRITY_KEY, manifest_str.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        return {
            'valid': False,
            'reason': 'Le manifeste d\'intégrité a été falsifié.',
            'tampered': ['MANIFEST'],
        }

    # Vérifier chaque fichier
    tampered = []
    for rel_path, expected_hash in files_manifest.items():
        full_path = base / rel_path
        if not full_path.exists():
            tampered.append(rel_path)
            continue
        actual_hash = _hash_file(full_path)
        if not hmac.compare_digest(actual_hash, expected_hash):
            tampered.append(rel_path)

    if tampered:
        return {
            'valid': False,
            'reason': f'{len(tampered)} fichier(s) modifié(s) : {", ".join(tampered)}',
            'tampered': tampered,
        }

    return {'valid': True, 'reason': 'Intégrité vérifiée.', 'tampered': []}


# ─── CLI pour générer le manifeste au build ──────────────────────────────────
if __name__ == '__main__':
    if '--generate' in sys.argv:
        generate_manifest()
    elif '--verify' in sys.argv:
        result = verify()
        if result['valid']:
            print("[Intégrité] ✓ Tous les fichiers sont intacts.")
        else:
            print(f"[Intégrité] ✗ ALERTE : {result['reason']}")
            sys.exit(1)
    else:
        print("Usage : python integrity_check.py --generate | --verify")
