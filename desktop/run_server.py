"""
MySchool - Lanceur Desktop Offline
Demarre le serveur Django sur localhost:8080 et ouvre le navigateur.
"""
import sys
import os
import time
import threading
import webbrowser
import socket

# Forcer l'encodage UTF-8 pour eviter les erreurs cp1252 sur Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def get_free_port(preferred=8080):
    """Trouve un port libre, en préférant le port spécifié."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('127.0.0.1', preferred))
        sock.close()
        return preferred
    except OSError:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        sock.close()
        return port


def setup_environment():
    """Configure l'environnement pour le mode desktop."""
    os.environ['DJANGO_SETTINGS_MODULE'] = 'desktop.settings_desktop'
    os.environ['MYSCHOOL_DESKTOP'] = '1'

    # Pour PyInstaller : ajouter le répertoire de l'app au sys.path
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)

    # Support WeasyPrint via MSYS2 si disponible
    msys_bin = r'C:\msys64\mingw64\bin'
    if os.path.exists(msys_bin):
        os.environ['PATH'] = msys_bin + os.pathsep + os.environ.get('PATH', '')


def run_migrations():
    """Applique les migrations de base de donnees."""
    from django.core.management import call_command
    print("[MySchool] Application des migrations...")
    call_command('migrate', '--run-syncdb', verbosity=1)
    print("[MySchool] Migrations terminees.")


def collect_static():
    """Collecte les fichiers statiques si necessaire."""
    from django.conf import settings
    static_root = str(settings.STATIC_ROOT)
    if not os.path.exists(static_root) or not os.listdir(static_root):
        from django.core.management import call_command
        print("[MySchool] Collecte des fichiers statiques...")
        call_command('collectstatic', '--noinput', verbosity=0)
        print("[MySchool] Fichiers statiques prets.")


def create_default_user():
    """Cree un utilisateur admin par defaut si la base est vide."""
    from django.contrib.auth.models import User
    if not User.objects.exists():
        print("[MySchool] Creation du compte administrateur par defaut...")
        user = User.objects.create_superuser(
            username='admin',
            email='admin@myschool.local',
            password='admin1234',
            first_name='Administrateur',
            last_name='MySchool'
        )
        try:
            from utilisateurs.models import Profil
            Profil.objects.create(
                user=user,
                role='ADMIN',
                telephone='+224000000000',
                actif=True,
                is_validated=True,
            )
        except Exception as e:
            print(f"[MySchool] Note: Profil non cree ({e})")

        print("[MySchool] +======================================+")
        print("[MySchool] |  Compte cree:                       |")
        print("[MySchool] |  Utilisateur: admin                 |")
        print("[MySchool] |  Mot de passe: admin1234            |")
        print("[MySchool] |  CHANGEZ-LE apres la 1ere connexion |")
        print("[MySchool] +======================================+")


def _find_modern_browser():
    """Cherche un navigateur moderne (Edge Chromium, Chrome, Firefox) sous Windows."""
    if os.name != 'nt':
        return None
    import shutil
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
    for name in ('msedge', 'chrome', 'firefox'):
        found = shutil.which(name)
        if found:
            return found
    return None


def open_browser(port):
    """Ouvre le navigateur après un court délai. Préfère un navigateur moderne sous Windows 10."""
    time.sleep(2.5)
    url = f'http://127.0.0.1:{port}/'
    print("[MySchool] Ouverture du navigateur: %s" % url)
    browser_path = _find_modern_browser()
    if browser_path:
        try:
            import subprocess
            subprocess.Popen([browser_path, url])
            print("[MySchool] Ouvert avec : %s" % os.path.basename(browser_path))
            return
        except Exception as e:
            print("[MySchool] Erreur lancement navigateur (%s), utilisation par défaut" % e)
    webbrowser.open(url)


def print_banner():
    """Affiche la banniere de demarrage."""
    print()
    print("+" + "=" * 52 + "+")
    print("|                                                    |")
    print("|        MySchool - Gestion Scolaire                 |")
    print("|        Version Desktop Hors-Ligne                  |")
    print("|                                                    |")
    print("+" + "=" * 52 + "+")
    print()


def main():
    print_banner()
    setup_environment()

    import django
    django.setup()

    # Mode setup uniquement (pour installer.bat / update.bat)
    if '--setup-only' in sys.argv:
        print("[MySchool] Mode configuration uniquement...")
        run_migrations()
        collect_static()
        create_default_user()
        print("[MySchool] Configuration terminee.")
        return

    # Démarrage normal
    run_migrations()
    collect_static()
    create_default_user()

    port = get_free_port(8080)

    # Ouvrir le navigateur dans un thread séparé
    threading.Thread(target=open_browser, args=(port,), daemon=True).start()

    print("[MySchool] Serveur demarre sur http://127.0.0.1:%d/" % port)
    print("[MySchool] Fermez cette fenetre pour arreter le serveur.")
    print()

    # Démarrer le serveur Django
    from django.core.management import call_command
    call_command('runserver', f'127.0.0.1:{port}', '--noreload')


if __name__ == '__main__':
    main()
