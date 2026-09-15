#!/usr/bin/env python
"""
MySchoolGN - Lanceur autonome offline
=======================================
Édition : GS Les Jardins Wosewa
Version : 1.0.0

Ce script lance le serveur Django en mode autonome (offline).
Conçu pour être compilé en .exe avec PyInstaller.
"""
import os
import sys
import threading
import time
import webbrowser
import socket
import hashlib
import hmac as _hmac_mod
import json as _json_mod
import secrets
import traceback
import datetime

# ─── Clé de garde anti-modification (obfusquée) ──────────────────────────────
def _gk_guard():
    _d = [138,190,148,164,175,168,168,171,128,137,152,134,169,179,174,147,
          166,170,183,162,181,152,128,178,166,181,163,152,245,247,245,243,
          152,148,162,164,178,181,162,152,140,162,190,152,177,246]
    return bytes(x ^ 0xC7 for x in _d)
_GUARD_KEY = _gk_guard()
del _gk_guard

# ─── Répertoire de base ────────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    # Mode exe PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
    # Ajouter le dossier _MEIPASS pour trouver les modules
    if hasattr(sys, '_MEIPASS'):
        sys.path.insert(0, sys._MEIPASS)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)

# ─── Mode sans console (windowed) : rediriger stdout/stderr vers un log ────────
# En build PyInstaller avec console=False, sys.stdout / sys.stderr / sys.stdin
# valent None. Tout print() ou input() lèverait alors une exception.
# On redirige donc les sorties vers un fichier log et on neutralise stdin.
if sys.stdout is None or sys.stderr is None:
    try:
        # buffering=1 : line-buffered → le log est écrit immédiatement (diagnostic fiable)
        _log_file = open(os.path.join(BASE_DIR, 'myschool.log'), 'a', encoding='utf-8', errors='replace', buffering=1)
        if sys.stdout is None:
            sys.stdout = _log_file
        if sys.stderr is None:
            sys.stderr = _log_file
    except Exception:
        class _NullWriter:
            def write(self, *_a, **_k):
                return 0
            def flush(self):
                pass
        if sys.stdout is None:
            sys.stdout = _NullWriter()
        if sys.stderr is None:
            sys.stderr = _NullWriter()

if sys.stdin is None:
    class _NullReader:
        def readline(self, *_a, **_k):
            return ''
        def read(self, *_a, **_k):
            return ''
    sys.stdin = _NullReader()


# ─── Certificats HTTPS : faire confiance au magasin de Windows ────────────────
# Python embarque son propre lot de certificats racine (via son OpenSSL). Sur
# un poste derriere un pare-feu ou un antivirus qui inspecte le trafic HTTPS
# avec son propre certificat, Windows (et donc un navigateur) lui fait
# confiance, mais Python non : toute connexion au serveur en ligne —
# synchronisation ou mise a jour — echoue alors silencieusement des le depart.
# `truststore` remplace la verification par celle du systeme d'exploitation,
# ce qui aligne Python sur ce que voit deja Windows. Doit avoir lieu avant le
# premier appel HTTPS de l'application, donc ici, au tout debut du module.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    # Environnement sans le module (ex. certains outils de build) : on
    # retombe sur le comportement standard de Python plutot que d'empecher
    # le demarrage pour un gain de robustesse qui n'est pas critique partout.
    pass

# ─── DLLs GTK pour WeasyPrint (Windows) ───────────────────────────────────────
# Doit être fait AVANT tout import de Django / WeasyPrint
if os.name == 'nt':
    # En mode EXE, les DLLs GTK sont dans _internal/ (PyInstaller --onedir)
    # En mode dev, elles sont dans MSYS2
    _dll_dirs = [BASE_DIR]
    if getattr(sys, 'frozen', False):
        _internal = os.path.join(BASE_DIR, '_internal')
        if os.path.isdir(_internal):
            _dll_dirs.append(_internal)
    else:
        # Mode développement : utiliser MSYS2 si disponible
        _msys2_bin = r'C:\msys64\mingw64\bin'
        if os.path.isdir(_msys2_bin):
            _dll_dirs.append(_msys2_bin)

    # Ajouter tous les répertoires au PATH
    for _d in _dll_dirs:
        if _d not in os.environ.get('PATH', ''):
            os.environ['PATH'] = _d + os.pathsep + os.environ.get('PATH', '')

    # Python 3.8+ : répertoire explicite pour les DLLs (plus fiable que PATH)
    if hasattr(os, 'add_dll_directory'):
        for _d in _dll_dirs:
            if os.path.isdir(_d):
                try:
                    os.add_dll_directory(_d)
                except Exception:
                    pass

    # GdkPixbuf loaders : configurer le chemin vers les loaders bundlés
    if getattr(sys, 'frozen', False):
        _loaders_dir = os.path.join(BASE_DIR, '_internal', 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders')
        if os.path.isdir(_loaders_dir):
            os.environ['GDK_PIXBUF_MODULE_FILE'] = os.path.join(
                os.path.dirname(_loaders_dir), 'loaders.cache'
            )
            os.environ['GDK_PIXBUF_MODULEDIR'] = _loaders_dir

# ─── Générer une SECRET_KEY stable par installation ───────────────────────────
_secret_file = os.path.join(BASE_DIR, '.secret_key')
if os.path.exists(_secret_file):
    with open(_secret_file, 'r') as _f:
        _secret_key = _f.read().strip()
else:
    _secret_key = 'sk-' + secrets.token_hex(32)
    try:
        with open(_secret_file, 'w') as _f:
            _f.write(_secret_key)
    except Exception:
        _secret_key = 'offline-fallback-key-myschool-gn-v1-' + hashlib.md5(
            BASE_DIR.encode()
        ).hexdigest()

# ─── Variables d'environnement Django ─────────────────────────────────────────
os.environ['DJANGO_SETTINGS_MODULE'] = 'ecole_moderne.settings'
os.environ['DJANGO_DEBUG'] = 'true'
os.environ['DJANGO_SECRET_KEY'] = _secret_key
os.environ['OFFLINE_MODE'] = '1'
os.environ['TWILIO_DISABLED'] = '1'
os.environ['OPENAI_DISABLED'] = '1'

# Dossier de données Django (DB, media, logs)
os.environ['MYSCHOOL_BASE_DIR'] = BASE_DIR


# ─── Configuration de synchronisation (par machine, sans recompilation) ───────
# Chaque poste definit son serveur EN LIGNE et son appareil via un fichier JSON
# local (jamais embarque dans le build). Cle attendues :
#   MYSCHOOL_SYNC_SERVER_URL, MYSCHOOL_SYNC_ECOLE_ID,
#   MYSCHOOL_SYNC_DEVICE_ID, MYSCHOOL_SYNC_TOKEN, MYSCHOOL_SYNC_INTERVAL,
#   MYSCHOOL_SYNC_FAST_INTERVAL
def _load_sync_config():
    import json
    candidates = [
        os.path.join(BASE_DIR, 'sync_config.json'),
        # Compatibilite avec les installations qui ont recu leur configuration
        # dans le sous-dossier `sync` sous le nom `_config.json`.
        os.path.join(BASE_DIR, 'sync', '_config.json'),
        os.path.join(BASE_DIR, 'sync', 'config.json'),
        os.path.join(os.environ.get('APPDATA', ''), 'MySchoolGN', 'sync_config.json'),
    ]
    keys = (
        'MYSCHOOL_SYNC_SERVER_URL', 'MYSCHOOL_SYNC_ECOLE_ID',
        'MYSCHOOL_SYNC_DEVICE_ID', 'MYSCHOOL_SYNC_TOKEN',
        'MYSCHOOL_SYNC_INTERVAL', 'MYSCHOOL_SYNC_FAST_INTERVAL',
        'MYSCHOOL_UPDATE_INTERVAL',
    )
    for path in candidates:
        try:
            if path and os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as _f:
                    data = json.load(_f)
                for key in keys:
                    value = data.get(key)
                    if value not in (None, ''):
                        os.environ.setdefault(key, str(value))
                break
        except Exception:
            pass

_load_sync_config()


# ─── Protection anti-modification (garde) ──────────────────────────────────────
def _tamper_exit():
    """Arrêt immédiat si modification détectée."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "MySchoolGN — Erreur critique",
            "L'application a été modifiée de manière non autorisée.\n\n"
            "L'application ne peut pas démarrer.\n\n"
            "Veuillez réinstaller MySchoolGN depuis le programme\n"
            "officiel du GS Les Jardins Wosewa."
        )
        root.destroy()
    except Exception:
        pass
    os._exit(1)


def _guard_check():
    """Vérification secondaire anti-modification (défense en profondeur)."""
    if not getattr(sys, 'frozen', False):
        return  # Mode développement

    guard_path = os.path.join(BASE_DIR, '.guard.dat')
    if not os.path.exists(guard_path):
        return  # Pas de fichier garde

    try:
        with open(guard_path, 'r', encoding='utf-8') as f:
            guard_data = _json_mod.load(f)

        stored_hash = guard_data.get('h', '')
        stored_sig = guard_data.get('s', '')

        # Vérifier la signature du fichier garde
        expected_sig = _hmac_mod.new(
            _GUARD_KEY, stored_hash.encode(), hashlib.sha256
        ).hexdigest()
        if not _hmac_mod.compare_digest(stored_sig, expected_sig):
            _tamper_exit()

        # Vérifier l'empreinte du module d'intégrité. Le moteur de licence ne
        # fait plus partie de l'application ni de cette chaîne de confiance.
        import integrity_check

        module_fp = _hmac_mod.new(
            _GUARD_KEY, integrity_check._INTEGRITY_KEY, hashlib.sha256
        ).hexdigest()

        if not _hmac_mod.compare_digest(module_fp, stored_hash):
            _tamper_exit()

    except (ImportError, FileNotFoundError):
        pass
    except Exception:
        pass


# ─── Vérification d'intégrité ──────────────────────────────────────────────────
def check_integrity():
    """Vérifie que les fichiers critiques n'ont pas été modifiés."""
    try:
        import integrity_check
        result = integrity_check.verify()
        if not result['valid']:
            print("")
            print("!" * 60)
            print("   ALERTE : Fichiers de l'application modifiés !")
            print("!" * 60)
            print(f"   {result['reason']}")
            print("")
            print("   L'application a été corrompue ou modifiée.")
            print("   Veuillez réinstaller depuis le programme officiel.")
            print("   Contact : GS Les Jardins Wosewa")
            print("!" * 60)
            print("")
            try:
                import tkinter as tk
                from tkinter import messagebox
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(
                    "MySchoolGN — Intégrité compromise",
                    "Des fichiers de l'application ont été modifiés.\n\n"
                    "L'application ne peut pas démarrer.\n\n"
                    "Veuillez réinstaller MySchoolGN depuis le programme\n"
                    "officiel du GS Les Jardins Wosewa."
                )
                root.destroy()
            except Exception:
                pass
            os._exit(1)
        else:
            if result.get('reason') != 'dev_mode':
                print("  [Intégrité] ✓ Vérification OK")
    except ImportError:
        pass  # Mode développement, integrity_check non disponible
    except Exception as e:
        print(f"  [Intégrité] Avertissement : {e}")


# ─── Utilitaires ──────────────────────────────────────────────────────────────
def find_free_port(start_port=8000, max_port=8100):
    """Trouve un port libre disponible."""
    for port in range(start_port, max_port):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    return start_port


def _app_version_stamp():
    """Empreinte de version (mtime de l'exe/script) pour n'exécuter certaines
    étapes lourdes qu'une fois par version installée."""
    try:
        ref = sys.executable if getattr(sys, 'frozen', False) else os.path.join(BASE_DIR, 'run_server.py')
        return str(int(os.path.getmtime(ref)))
    except Exception:
        return '0'


def _static_is_ready():
    """Vrai si collectstatic a déjà été fait pour cette version de l'app."""
    try:
        marker = os.path.join(BASE_DIR, '.static_ready')
        if os.path.exists(marker):
            with open(marker, 'r', encoding='utf-8') as f:
                return f.read().strip() == _app_version_stamp()
    except Exception:
        pass
    return False


def _mark_static_ready():
    try:
        with open(os.path.join(BASE_DIR, '.static_ready'), 'w', encoding='utf-8') as f:
            f.write(_app_version_stamp())
    except Exception:
        pass


def setup_database():
    """Initialise la base SQLite — migration UNIQUEMENT si nécessaire.

    Démarrage rapide : on ne migre (et ne sauvegarde la DB) que s'il existe des
    migrations en attente ; collectstatic n'est refait qu'à chaque nouvelle
    version de l'application. Cela évite ~6 s de surcoût à chaque lancement.
    """
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import connection

    # Chemin réel de la base selon Django (robuste quel que soit le layout)
    try:
        real_db_path = str(connection.settings_dict.get('NAME') or '')
    except Exception:
        real_db_path = os.path.join(BASE_DIR, 'db.sqlite3')
    is_new_db = not os.path.exists(real_db_path) or os.path.getsize(real_db_path) == 0

    # Y a-t-il des migrations en attente ? (vérif rapide ~0,3 s)
    pending = True
    if not is_new_db:
        try:
            from django.db.migrations.executor import MigrationExecutor
            executor = MigrationExecutor(connection)
            targets = executor.loader.graph.leaf_nodes()
            pending = bool(executor.migration_plan(targets))
        except Exception:
            pending = True  # en cas de doute, migrer

    if is_new_db or pending:
        # Sauvegarde de la DB uniquement AVANT une vraie migration
        if not is_new_db:
            backup_dir = os.path.join(BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)
            import shutil
            backup_name = f"db_avant_migration_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.sqlite3"
            backup_path = os.path.join(backup_dir, backup_name)
            try:
                shutil.copy2(real_db_path, backup_path)
                print(f"[MySchoolGN] Sauvegarde DB → {backup_name}")
                _cleanup_old_backups(backup_dir, prefix='db_avant_migration_', keep=5)
            except Exception as e:
                print(f"[MySchoolGN] Avertissement sauvegarde DB : {e}")

        print("[MySchoolGN] Migration de la base de données...")
        call_command('migrate', '--run-syncdb', verbosity=0)
    else:
        print("[MySchoolGN] Base de données à jour — démarrage rapide.")

    if is_new_db:
        print("[MySchoolGN] Nouvelle installation détectée.")
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(username='admin').exists():
                User.objects.create_superuser(
                    username='admin',
                    password='admin1234',
                    email='admin@myschool.local'
                )
                print("[MySchoolGN] Compte admin créé : admin / admin1234")
        except Exception as e:
            print(f"[MySchoolGN] Avertissement création admin : {e}")

    # Fichiers statiques : une seule fois par version de l'application
    if not _static_is_ready():
        print("[MySchoolGN] Préparation des fichiers statiques...")
        try:
            call_command('collectstatic', '--noinput', verbosity=0)
            _mark_static_ready()
        except Exception:
            pass


def _cleanup_old_backups(backup_dir, prefix='db_avant_migration_', keep=5):
    """Supprime les anciennes sauvegardes automatiques, garde les N plus récentes."""
    try:
        backups = sorted([
            f for f in os.listdir(backup_dir)
            if f.startswith(prefix) and f.endswith('.sqlite3')
        ])
        for old in backups[:-keep]:
            os.remove(os.path.join(backup_dir, old))
    except Exception:
        pass


def _find_modern_browser():
    """Cherche un navigateur moderne (Edge Chromium, Chrome, Firefox) sous Windows."""
    if os.name != 'nt':
        return None
    import shutil
    import subprocess
    # Chemins connus des navigateurs modernes sous Windows
    candidates = [
        # Edge Chromium
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        # Google Chrome
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        # Firefox
        os.path.join(os.environ.get('PROGRAMFILES', ''), 'Mozilla Firefox', 'firefox.exe'),
        os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Mozilla Firefox', 'firefox.exe'),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    # Tenter via PATH
    for name in ('msedge', 'chrome', 'firefox'):
        found = shutil.which(name)
        if found:
            return found
    return None


def _wait_server_ready(port, timeout=30.0):
    """Attend que le serveur Django réponde sur le port avant d'ouvrir la fenêtre."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    return True
        except OSError:
            pass
        time.sleep(0.3)
    return False


def open_browser(port):
    """Ouvre l'application dans sa PROPRE fenêtre (mode application).

    Utilise Edge/Chrome en mode --app= : une fenêtre dédiée sans barre
    d'adresse ni onglets, comme une application native (pas le navigateur).
    """
    # Attendre que le serveur réponde plutôt qu'un simple sleep fixe
    if not _wait_server_ready(port, timeout=30.0):
        time.sleep(2.5)
    url = f'http://127.0.0.1:{port}'
    print(f"[MySchoolGN] Ouverture de la fenêtre → {url}")

    # Profil dédié pour garantir une fenêtre isolée (ne se fond pas dans
    # une fenêtre Edge/Chrome déjà ouverte avec des onglets)
    profile_dir = os.path.join(BASE_DIR, '.appwindow')
    try:
        os.makedirs(profile_dir, exist_ok=True)
    except Exception:
        profile_dir = None

    browser_path = _find_modern_browser()
    # Edge et Chrome (Chromium) supportent --app= ; Firefox non.
    if browser_path and os.path.basename(browser_path).lower() in (
            'msedge.exe', 'chrome.exe', 'msedge', 'chrome'):
        try:
            import subprocess
            args = [
                browser_path,
                f'--app={url}',
                '--window-size=1280,820',
                '--no-first-run',
                '--no-default-browser-check',
            ]
            if profile_dir:
                args.append(f'--user-data-dir={profile_dir}')
            subprocess.Popen(args)
            print(f"[MySchoolGN] Fenêtre ouverte avec : {os.path.basename(browser_path)} (mode application)")
            return
        except Exception as e:
            print(f"[MySchoolGN] Erreur ouverture fenêtre application ({e}), repli navigateur")

    # Repli : ouvrir dans le navigateur par défaut
    if browser_path:
        try:
            import subprocess
            subprocess.Popen([browser_path, url])
            print(f"[MySchoolGN] Ouvert avec : {os.path.basename(browser_path)}")
            return
        except Exception as e:
            print(f"[MySchoolGN] Erreur lancement navigateur ({e}), utilisation par défaut")
    webbrowser.open(url)


def show_banner(port):
    """Affiche la bannière de démarrage."""
    print("")
    print("=" * 60)
    print("   MySchoolGN - Système de Gestion Scolaire")
    print("   Accès actif — aucune licence requise")
    print("=" * 60)
    print("")
    print(f"   Adresse : http://127.0.0.1:{port}")
    print(f"   Admin   : http://127.0.0.1:{port}/admin/")
    print("")
    print("   Identifiants par défaut :")
    print("     Utilisateur : admin")
    print("     Mot de passe: admin1234")
    print("")
    print("   Appuyez sur Ctrl+C pour arrêter le serveur")
    print("=" * 60)
    print("")


# ─── Affichage d'erreur fatale (mode sans console) ─────────────────────────────
def _show_fatal_error(message):
    """Affiche une erreur dans une fenêtre (pas de console en mode windowed)."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("MySchoolGN — Erreur", message)
        root.destroy()
    except Exception:
        pass


# ─── Sous-commandes de maintenance ────────────────────────────────────────────
def _traiter_sous_commande():
    """Exécute une sous-commande de sauvegarde passée en argument, si présente.

    Traitée avant tout le reste — garde d'intégrité, base et serveur — afin
    qu'une tâche planifiée puisse sauvegarder sans ouvrir l'application.

    Le moteur de sauvegarde n'utilise ni Django ni la découverte des commandes
    de management : il fonctionne donc dans l'exécutable PyInstaller.

    Retourne True si une sous-commande a été traitée (l'application ne doit pas
    démarrer le serveur).
    """
    arguments = [a.lower() for a in sys.argv[1:]]
    if not arguments:
        return False

    connues = {'--sauvegarder', '--restaurer', '--lister-sauvegardes', '--diagnostiquer-sync'}
    demandee = next((a for a in arguments if a in connues), None)
    if not demandee:
        return False

    if demandee == '--diagnostiquer-sync':
        # A la difference des autres sous-commandes, celle-ci a besoin de
        # Django (modeles, parametres) pour rejouer un cycle de
        # synchronisation reel. `django.setup()` n'a normalement lieu que
        # plus loin, dans `setup_database()` : on l'avance ici.
        import django
        django.setup()
        from synchronisation import auto_sync
        sys.exit(auto_sync.diagnostiquer_synchronisation())

    from ecole_moderne import sauvegarde

    if demandee == '--lister-sauvegardes':
        print("[Sauvegarde] Destinations :")
        for cible in sauvegarde.destinations():
            etat = 'existe' if os.path.isdir(cible) else 'a creer'
            print(f"  - {cible}  [{etat}]")
        archives = sauvegarde.archives_disponibles()
        print(f"[Sauvegarde] Archives disponibles : {len(archives)}")
        for archive in archives[:20]:
            print(f"  {archive['date']:%d/%m/%Y %H:%M}  "
                  f"{archive['taille'] / (1024 * 1024):6.1f} Mo  {archive['chemin']}")
        return True

    if demandee == '--sauvegarder':
        rapport = sauvegarde.executer_sauvegarde()
        for avertissement in rapport.avertissements:
            print(f"[Sauvegarde] Avertissement : {avertissement}")
        for echec in rapport.destinations_ko:
            print(f"[Sauvegarde] Destination en echec : {echec}")
        print(f"[Sauvegarde] {rapport.resume()}")
        sys.exit(0 if rapport.succes else 1)

    # --restaurer [chemin] [--confirmer]
    positionnels = [a for a in sys.argv[1:] if not a.startswith('--')]
    chemin = positionnels[0] if positionnels else None
    if not chemin:
        disponibles = sauvegarde.archives_disponibles()
        if not disponibles:
            print("[Restauration] Aucune archive trouvee sur les destinations connues.")
            sys.exit(1)
        chemin = disponibles[0]['chemin']

    try:
        manifeste = sauvegarde.lire_manifeste(chemin)
    except Exception as err:
        print(f"[Restauration] Archive illisible : {err}")
        sys.exit(1)

    print(f"[Restauration] Archive : {chemin}")
    print(f"  Date    : {manifeste.get('date', '?')}")
    print(f"  Machine : {manifeste.get('machine', '?')}")
    print(f"  Medias  : {(manifeste.get('media') or {}).get('nombre', '?')} fichier(s)")
    for cle, valeur in (manifeste.get('statistiques') or {}).items():
        print(f"  {cle:<9} : {valeur}")

    if '--confirmer' not in arguments:
        print("[Restauration] Rien n'a ete modifie. Ajoutez --confirmer pour restaurer.")
        sys.exit(0)

    rapport = sauvegarde.restaurer(chemin)
    if rapport.erreur:
        print(f"[Restauration] ECHEC : {rapport.erreur}")
        sys.exit(1)
    print("[Restauration] Terminee. Redemarrez MySchoolGN.")
    sys.exit(0)


# ─── Point d'entrée principal ──────────────────────────────────────────────────
def main():
    """Point d'entrée principal."""
    if _traiter_sous_commande():
        return

    print("")
    print("*" * 60)
    print("   MySchoolGN — GS Les Jardins Wosewa")
    print("   Démarrage en mode offline...")
    print("*" * 60)
    print(f"   Répertoire : {BASE_DIR}")

    # ── Mise à jour téléchargée lors d'une session précédente ────────────────
    # Appliquée ici, avant que quoi que ce soit ne démarre : l'installateur
    # remplace des fichiers que l'application verrouillerait, et c'est le seul
    # moment où personne n'est en train de saisir. L'application s'arrête, et
    # l'installateur la rouvre une fois la nouvelle version en place.
    try:
        from ecole_moderne import auto_mise_a_jour
        if auto_mise_a_jour.appliquer_si_en_attente():
            print("[MAJ] Une nouvelle version s'installe. L'application va redémarrer.")
            return
    except Exception as _maj_err:
        print(f"[MAJ] Mise à jour en attente non appliquée : {_maj_err}")

    # Vérification anti-modification (garde)
    _guard_check()

    # Vérification d'intégrité (anti-modification)
    check_integrity()

    # Créer les dossiers nécessaires
    for folder in ['logs', 'media', 'staticfiles',
                   'media/photos_eleves', 'media/logos_ecoles']:
        folder_path = os.path.join(BASE_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)

    # Trouver un port libre
    port = find_free_port()

    # Initialiser la base de données
    try:
        setup_database()
    except Exception as e:
        print(f"[MySchoolGN] Erreur initialisation : {e}")
        traceback.print_exc()  # Traceback complète (la vraie cause) dans myschool.log
        print("[MySchoolGN] Tentative de démarrage sans migration...")

    # Afficher la bannière
    show_banner(port)

    # Démarrer la synchronisation automatique en arrière-plan (si configurée).
    # Le worker tente push+pull périodiquement ; hors-ligne il réessaie et se
    # synchronise automatiquement dès que la connexion revient.
    try:
        from synchronisation import auto_sync
        try:
            _sync_interval = int(os.environ.get('MYSCHOOL_SYNC_INTERVAL', '10'))
        except (TypeError, ValueError):
            _sync_interval = 10
        try:
            _sync_fast = int(os.environ.get('MYSCHOOL_SYNC_FAST_INTERVAL', '2'))
        except (TypeError, ValueError):
            _sync_fast = 2
        if auto_sync.start(interval=_sync_interval, boot_delay=8, fast_interval=_sync_fast):
            # Les cadences annoncées sont celles réellement appliquées, bornes
            # comprises, et non les valeurs brutes du fichier de configuration.
            _repos, _actif = auto_sync.cadence_effective(_sync_interval, _sync_fast)
            print(f"[Sync] Synchronisation automatique active "
                  f"(envoi immediat, verification {_actif}s en activite, "
                  f"{_repos}s au repos).")
    except Exception as _sync_err:
        print(f"[Sync] Synchronisation automatique non démarrée : {_sync_err}")

    # Surveiller les nouvelles versions de l'application. Le téléchargement se
    # fait en tâche de fond ; l'installation attend le prochain démarrage, seul
    # moment où interrompre l'application ne coûte aucune saisie.
    try:
        from ecole_moderne import auto_mise_a_jour
        try:
            _maj_interval = int(os.environ.get('MYSCHOOL_UPDATE_INTERVAL', str(6 * 3600)))
        except (TypeError, ValueError):
            _maj_interval = 6 * 3600
        if auto_mise_a_jour.start(intervalle=_maj_interval, delai_initial=90):
            print(f"[MAJ] Recherche de mises à jour active (toutes les {_maj_interval // 60} min).")
    except Exception as _maj_err:
        print(f"[MAJ] Recherche de mises à jour non démarrée : {_maj_err}")

    # Démarrer la sauvegarde automatique en arrière-plan. Complémentaire de la
    # tâche planifiée Windows : celle-ci couvre l'application fermée, celle-là
    # ne demande aucune installation ni droit administrateur sur le poste.
    try:
        from ecole_moderne import auto_sauvegarde
        _sauv_heures = auto_sauvegarde.start()
        if _sauv_heures:
            print(f"[Sauvegarde] Sauvegarde automatique active (toutes les "
                  f"{_sauv_heures:g} h, base + medias, destinations multiples).")
    except Exception as _sauv_err:
        print(f"[Sauvegarde] Sauvegarde automatique non démarrée : {_sauv_err}")

    # Ouvrir le navigateur en arrière-plan
    browser_thread = threading.Thread(
        target=open_browser, args=(port,), daemon=True
    )
    browser_thread.start()

    # Lancer le serveur Django
    try:
        import django
        from django.apps import apps as _apps
        # django.setup() a déjà été appelé dans setup_database().
        # On ne le rappelle QUE si le registre n'est pas prêt, pour éviter
        # l'erreur "populate() isn't reentrant" qui masquerait la vraie cause.
        if not _apps.ready:
            django.setup()
        from django.core.management import call_command
        call_command('runserver', f'127.0.0.1:{port}', '--noreload')
    except KeyboardInterrupt:
        print("\n[MySchoolGN] Arrêt du serveur...")
        print("[MySchoolGN] Au revoir !")
    except Exception as e:
        print(f"\n[MySchoolGN] Erreur : {e}")
        traceback.print_exc()  # Traceback complète dans myschool.log (diagnostic)
        _show_fatal_error(f"Erreur au démarrage du serveur :\n\n{e}")


if __name__ == '__main__':
    _log_path = os.path.join(BASE_DIR, 'startup_error.log')
    try:
        main()
    except SystemExit:
        raise
    except Exception as _crash:
        _msg = (
            f"[{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
            f"CRASH AU DÉMARRAGE\n"
            f"{traceback.format_exc()}\n"
        )
        try:
            with open(_log_path, 'a', encoding='utf-8') as _f:
                _f.write(_msg)
        except Exception:
            pass
        print(_msg)
        _show_fatal_error(
            "MySchoolGN n'a pas pu démarrer.\n\n"
            f"Détail technique :\n{_crash}\n\n"
            f"Un rapport a été enregistré dans :\n{_log_path}"
        )
