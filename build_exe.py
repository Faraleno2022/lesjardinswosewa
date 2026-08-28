#!/usr/bin/env python
"""
MySchoolGN - Script de compilation automatique
===============================================
Ce script automatise la compilation de l'application en .exe
avec PyInstaller et prepare le dossier de distribution.
"""

import hashlib
import io
import os
import re
import sys
import shutil
import subprocess

# Repertoire du projet
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(BASE_DIR, 'dist')
BUILD_DIR = os.path.join(BASE_DIR, 'build')
OUTPUT_DIR = os.path.join(DIST_DIR, 'MySchoolGN')


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def check_prereqs():
    """Verifie les prerequis."""
    step("Verification des prerequis")

    # Verifier PyInstaller
    try:
        import PyInstaller
        print(f"  [OK] PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  [MANQUANT] PyInstaller - Installation en cours...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        print("  [OK] PyInstaller installe")

    # Verifier Django
    try:
        import django
        print(f"  [OK] Django {django.get_version()}")
    except ImportError:
        print("  [ERREUR] Django non installe!")
        sys.exit(1)

    # Verifier les autres dependances critiques
    for pkg_name, import_name in [('reportlab', 'reportlab'), ('openpyxl', 'openpyxl'),
                                   ('Pillow', 'PIL'), ('python-dotenv', 'dotenv')]:
        try:
            __import__(import_name)
            print(f"  [OK] {pkg_name}")
        except ImportError:
            print(f"  [MANQUANT] {pkg_name} - Installation...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', pkg_name])


def collect_static():
    """Collecte les fichiers statiques Django."""
    step("Collecte des fichiers statiques")
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
    os.environ['DJANGO_DEBUG'] = 'true'
    os.environ['DJANGO_SECRET_KEY'] = 'build-key-temp'

    try:
        subprocess.check_call([
            sys.executable, 'manage.py', 'collectstatic', '--noinput'
        ], cwd=BASE_DIR)
        print("  [OK] Fichiers statiques collectes")
    except subprocess.CalledProcessError:
        print("  [AVERTISSEMENT] Erreur lors de collectstatic (non critique)")


def run_pyinstaller():
    """Execute PyInstaller avec le fichier spec."""
    step("Compilation avec PyInstaller")

    spec_file = os.path.join(BASE_DIR, 'myschool.spec')
    if not os.path.exists(spec_file):
        print(f"  [ERREUR] Fichier spec introuvable: {spec_file}")
        print("  Utilisez le fichier myschool.spec versionne avec le projet.")
        sys.exit(1)

    # Nettoyer les anciens builds
    for d in [BUILD_DIR, os.path.join(DIST_DIR, 'MySchoolGN')]:
        if os.path.exists(d):
            print(f"  Suppression de {d}...")
            shutil.rmtree(d)

    # Lancer PyInstaller
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--clean',
        '--noconfirm',
        spec_file
    ]
    print(f"  Commande: {' '.join(cmd)}")
    subprocess.check_call(cmd, cwd=BASE_DIR)
    print("  [OK] Compilation terminee")


def copy_extra_files():
    """Copie les fichiers supplementaires dans le dossier de distribution."""
    step("Copie des fichiers supplementaires")

    if not os.path.exists(OUTPUT_DIR):
        print(f"  [ERREUR] Dossier de sortie introuvable: {OUTPUT_DIR}")
        return

    # Copier les templates (au cas ou PyInstaller les aurait manques)
    templates_src = os.path.join(BASE_DIR, 'templates')
    templates_dst = os.path.join(OUTPUT_DIR, 'templates')
    if os.path.exists(templates_src) and not os.path.exists(templates_dst):
        shutil.copytree(templates_src, templates_dst)
        print("  [OK] Templates copies")

    # Copier les fichiers statiques
    static_src = os.path.join(BASE_DIR, 'static')
    static_dst = os.path.join(OUTPUT_DIR, 'static')
    if os.path.exists(static_src) and not os.path.exists(static_dst):
        shutil.copytree(static_src, static_dst)
        print("  [OK] Fichiers statiques copies")

    # Ne copier que les ressources generiques. Le dossier media du poste de
    # compilation contient des photos d'eleves, logos d'ecoles et documents
    # reels qui ne doivent jamais etre livres dans l'installateur generique.
    generic_media = [
        (os.path.join('ecoles', 'default'), os.path.join('ecoles', 'default')),
        (os.path.join('eleves', 'default'), os.path.join('eleves', 'default')),
    ]
    for source_rel, destination_rel in generic_media:
        source = os.path.join(BASE_DIR, 'media', source_rel)
        destination = os.path.join(OUTPUT_DIR, 'media', destination_rel)
        if os.path.isdir(source):
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copytree(source, destination, dirs_exist_ok=True)
    print("  [OK] Medias generiques copies (aucune donnee d'ecole)")

    # NE PAS copier la base de données du développeur dans le build
    # run_server.py créera une base vierge via 'migrate' au premier démarrage
    db_paths = [
        os.path.join(OUTPUT_DIR, 'db.sqlite3'),
        os.path.join(OUTPUT_DIR, '_internal', 'db.sqlite3'),
    ]
    for db_dst in db_paths:
        if os.path.exists(db_dst):
            os.remove(db_dst)
            print("  [INFO] db.sqlite3 du dev supprimee du build (sera creee au 1er demarrage)")

    # Ne jamais livrer d'anciens fichiers locaux du poste de compilation.
    for dev_file in ['license.dat', '.trial_start', '.secret_key', '.env']:
        dev_dst = os.path.join(OUTPUT_DIR, dev_file)
        if os.path.exists(dev_dst):
            os.remove(dev_dst)
            print(f"  [INFO] {dev_file} du dev supprime du build")

    # Ne jamais embarquer par defaut le jeton d'une ecole dans l'installateur
    # generique. Un build volontairement personnalise reste possible avec
    # MYSCHOOL_EMBED_SYNC_CONFIG=1.
    sync_config_src = os.path.join(BASE_DIR, 'sync_config.json')
    sync_config_dst = os.path.join(OUTPUT_DIR, 'sync_config.json')
    embed_sync_config = os.environ.get(
        'MYSCHOOL_EMBED_SYNC_CONFIG', '',
    ).strip().lower() in {'1', 'true', 'yes', 'oui'}
    if embed_sync_config and os.path.exists(sync_config_src):
        shutil.copy2(sync_config_src, sync_config_dst)
        print("  [OK] Configuration de synchronisation client copiee")
    elif os.path.exists(sync_config_dst):
        os.remove(sync_config_dst)
        print("  [OK] Build generique : aucune configuration d'ecole embarquee")

    # Creer les dossiers necessaires
    for folder in ['logs', 'media', 'backups']:
        folder_path = os.path.join(OUTPUT_DIR, folder)
        os.makedirs(folder_path, exist_ok=True)

    print("  [OK] Fichiers supplementaires copies")


def verify_static_images():
    """Verifie que chaque image source est livree sans alteration."""
    step("Verification des images integrees")

    source_root = os.path.join(BASE_DIR, 'static', 'images')
    destination_root = os.path.join(OUTPUT_DIR, 'static', 'images')
    if not os.path.isdir(source_root):
        raise RuntimeError(f"Dossier d'images source introuvable: {source_root}")
    if not os.path.isdir(destination_root):
        raise RuntimeError(
            f"Dossier d'images absent de la distribution: {destination_root}"
        )

    source_files = sorted(
        os.path.relpath(os.path.join(root, filename), source_root)
        for root, _, filenames in os.walk(source_root)
        for filename in filenames
    )
    if not source_files:
        raise RuntimeError("Aucune image trouvee dans static/images")

    total_bytes = 0
    for relative_path in source_files:
        source_path = os.path.join(source_root, relative_path)
        destination_path = os.path.join(destination_root, relative_path)
        if not os.path.isfile(destination_path):
            raise RuntimeError(f"Image absente du build: {relative_path}")

        with open(source_path, 'rb') as source_file:
            source_digest = hashlib.sha256(source_file.read()).digest()
        with open(destination_path, 'rb') as destination_file:
            destination_digest = hashlib.sha256(destination_file.read()).digest()
        if source_digest != destination_digest:
            raise RuntimeError(f"Image alteree dans le build: {relative_path}")
        total_bytes += os.path.getsize(source_path)

    print(
        f"  [OK] {len(source_files)} images verifiees octet par octet "
        f"({total_bytes} octets)"
    )


def create_launcher_bat():
    """Cree un fichier .bat de lancement facile."""
    step("Creation du lanceur .bat")

    bat_content = '''@echo off
title MySchoolGN - Systeme de Gestion Scolaire
echo.
echo ============================================================
echo    MySchoolGN - Systeme de Gestion Scolaire
echo    Version Offline
echo ============================================================
echo.
echo Demarrage du serveur...
echo.
cd /d "%~dp0"
MySchoolGN.exe
pause
'''
    bat_path = os.path.join(OUTPUT_DIR, 'Demarrer_MySchoolGN.bat')
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f"  [OK] Lanceur cree: {bat_path}")


def create_stop_bat():
    """Cree un fichier .bat pour arreter le serveur."""
    bat_content = '''@echo off
echo Arret de MySchoolGN...
taskkill /F /IM MySchoolGN.exe >nul 2>&1
echo Serveur arrete.
timeout /t 2 >nul
'''
    bat_path = os.path.join(OUTPUT_DIR, 'Arreter_MySchoolGN.bat')
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(bat_content)
    print(f"  [OK] Script d'arret cree: {bat_path}")


def copy_gtk_dlls():
    """Copie les DLLs GTK/Pango/Cairo pour WeasyPrint offline."""
    step("Copie des DLLs GTK pour WeasyPrint")

    gtk_dll_dir = r'C:\msys64\mingw64\bin'
    internal_dir = os.path.join(OUTPUT_DIR, '_internal')

    if not os.path.isdir(gtk_dll_dir):
        print("  [AVERTISSEMENT] MSYS2 non trouve - DLLs GTK non copiees")
        return

    gtk_dlls = [
        'libpango-1.0-0.dll', 'libpangocairo-1.0-0.dll',
        'libpangoft2-1.0-0.dll', 'libpangowin32-1.0-0.dll',
        'libcairo-2.dll', 'libcairo-gobject-2.dll',
        'libgobject-2.0-0.dll', 'libglib-2.0-0.dll',
        'libgio-2.0-0.dll', 'libgmodule-2.0-0.dll',
        'libgdk_pixbuf-2.0-0.dll', 'libfontconfig-1.dll',
        'libfreetype-6.dll', 'libfribidi-0.dll',
        'libharfbuzz-0.dll', 'libintl-8.dll',
        'libiconv-2.dll', 'libpixman-1-0.dll',
        'libpng16-16.dll', 'libexpat-1.dll',
        'libpcre2-8-0.dll', 'zlib1.dll',
        'libffi-8.dll', 'libgraphite2.dll',
        'libbrotlidec.dll', 'libbrotlicommon.dll',
        'libbz2-1.dll', 'libstdc++-6.dll',
        'libgcc_s_seh-1.dll', 'libwinpthread-1.dll',
    ]

    copied = 0
    for dll in gtk_dlls:
        src = os.path.join(gtk_dll_dir, dll)
        dst = os.path.join(internal_dir, dll)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
            copied += 1
    print(f"  [OK] {copied} DLLs GTK copiees dans _internal/")

    # Copier les loaders GdkPixbuf
    loaders_src = r'C:\msys64\mingw64\lib\gdk-pixbuf-2.0\2.10.0\loaders'
    loaders_dst = os.path.join(internal_dir, 'lib', 'gdk-pixbuf-2.0', '2.10.0', 'loaders')
    if os.path.isdir(loaders_src) and not os.path.isdir(loaders_dst):
        shutil.copytree(loaders_src, loaders_dst)
        # Copier aussi le loaders.cache
        cache_src = os.path.join(os.path.dirname(loaders_src), 'loaders.cache')
        if os.path.exists(cache_src):
            shutil.copy2(cache_src, os.path.join(os.path.dirname(loaders_dst), 'loaders.cache'))
        print("  [OK] GdkPixbuf loaders copies")


def compiler_installateur():
    """
    Produit l'installateur Windows avec Inno Setup.

    Cette etape se faisait a la main. La laisser dehors coutait cher depuis
    que les postes se mettent a jour tout seuls : l'empreinte publiee dans
    l'administration doit etre celle d'un fichier reellement compile, et un
    installateur oublie signifie une version annoncee que personne ne peut
    telecharger.

    Inno Setup n'est pas toujours dans le PATH ; on le cherche la ou son
    programme d'installation le depose.
    """
    step('Installateur Windows')

    candidats = [
        shutil.which('ISCC'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Inno Setup 6', 'ISCC.exe'),
        r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe',
        r'C:\Program Files\Inno Setup 6\ISCC.exe',
        r'C:\InnoSetup6\ISCC.exe',
    ]
    iscc = next((c for c in candidats if c and os.path.exists(c)), None)
    if not iscc:
        print('  [INFO] Inno Setup introuvable : installateur non compile.')
        print('         https://jrsoftware.org/isinfo.php, puis relancez ce script.')
        return False

    script = os.path.join(BASE_DIR, 'installer_myschool.iss')
    if not os.path.exists(script):
        print('  [INFO] installer_myschool.iss absent : etape ignoree')
        return False

    print(f'  Compilateur : {iscc}')
    resultat = subprocess.run(
        [iscc, script], cwd=BASE_DIR,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
    )
    if resultat.returncode != 0:
        print('  [ERREUR] Inno Setup a echoue :')
        for ligne in (resultat.stdout or '').splitlines()[-15:]:
            print(f'    {ligne}')
        for ligne in (resultat.stderr or '').splitlines()[-10:]:
            print(f'    {ligne}')
        return False

    print('  [OK] Installateur compile dans Output/')
    return True


def show_summary():
    """Affiche le resume de la compilation."""
    step("COMPILATION TERMINEE")

    # Calculer la taille du dossier
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(OUTPUT_DIR):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    size_mb = total_size / (1024 * 1024)

    print(f"  Dossier de sortie: {OUTPUT_DIR}")
    print(f"  Taille totale:     {size_mb:.1f} Mo")
    print(f"")
    print(f"  Fichiers principaux:")
    print(f"    - MySchoolGN.exe           (Application)")
    print(f"    - Demarrer_MySchoolGN.bat  (Lanceur)")
    print(f"    - Arreter_MySchoolGN.bat   (Arret)")
    print(f"")
    print(f"  Pour tester:")
    print(f"    1. Ouvrez le dossier: {OUTPUT_DIR}")
    print(f"    2. Double-cliquez sur 'Demarrer_MySchoolGN.bat'")
    print(f"    3. Le navigateur s'ouvrira sur http://127.0.0.1:8000")
    print(f"")
    print("  Installateur : dossier Output/")
    print(f"")


def generate_integrity_manifest():
    """Genere le manifeste d'integrite dans le dossier de distribution."""
    step("Generation du manifeste d'integrite")

    if not os.path.exists(OUTPUT_DIR):
        print("  [ERREUR] Dossier de sortie introuvable")
        return

    # Copier integrity_check.py TEMPORAIREMENT pour generer le manifeste
    ic_src = os.path.join(BASE_DIR, 'integrity_check.py')
    ic_dst = os.path.join(OUTPUT_DIR, 'integrity_check.py')
    if os.path.exists(ic_src):
        shutil.copy2(ic_src, ic_dst)

    # Generer le manifeste depuis le dossier de distribution
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = OUTPUT_DIR
        env['PYTHONIOENCODING'] = 'utf-8'
        env['PYTHONUTF8'] = '1'
        subprocess.check_call(
            [sys.executable, ic_dst, '--generate'],
            cwd=OUTPUT_DIR,
            env=env,
        )
        print("  [OK] Manifeste d'integrite genere")
    except subprocess.CalledProcessError as e:
        print(f"  [AVERTISSEMENT] Erreur generation manifeste : {e}")
    except Exception as e:
        print(f"  [AVERTISSEMENT] {e}")


def protect_source_files():
    """Supprime les fichiers source .py lisibles de la distribution.

    PROTECTION ANTI-MODIFICATION : Les modules critiques sont compiles
    en bytecode dans le PYZ par PyInstaller (via hiddenimports).
    Les copies .py lisibles sont supprimees pour empecher un attaquant
    de les ouvrir dans un editeur et modifier le code.
    """
    step("Protection anti-modification des fichiers source")

    if not os.path.exists(OUTPUT_DIR):
        print("  [ERREUR] Dossier de sortie introuvable")
        return

    critical_files = [
        'integrity_check.py',
        'load_env.py',
    ]

    removed = []
    for fname in critical_files:
        for location in [OUTPUT_DIR, os.path.join(OUTPUT_DIR, '_internal')]:
            fpath = os.path.join(location, fname)
            if os.path.exists(fpath):
                os.remove(fpath)
                removed.append(os.path.relpath(fpath, OUTPUT_DIR))

    for r in removed:
        print(f"  [OK] Source supprime : {r}")

    if not removed:
        print("  [INFO] Aucun fichier source expose trouve")

    print(f"  [OK] {len(removed)} fichier(s) source supprime(s) de la distribution")


def generate_guard_file():
    """Genere le fichier de garde .guard.dat pour la verification anti-modification.

    Ce fichier contient l'empreinte HMAC du module d'integrite critique.
    Il est verifie par run_server.py (compile dans l'EXE) au demarrage.
    La cle de garde reste differente de la cle d'integrite.
    """
    step("Generation du fichier de garde anti-modification")

    if not os.path.exists(OUTPUT_DIR):
        print("  [ERREUR] Dossier de sortie introuvable")
        return

    import hmac as _hmac
    import hashlib as _hl
    import json

    # Cle de garde (identique a celle dans run_server.py)
    def _gk():
        _d = [138,190,148,164,175,168,168,171,128,137,152,134,169,179,174,147,
              166,170,183,162,181,152,128,178,166,181,163,152,245,247,245,243,
              152,148,162,164,178,181,162,152,140,162,190,152,177,246]
        return bytes(x ^ 0xC7 for x in _d)
    guard_key = _gk()

    # Importer les modules depuis les sources du projet
    _saved_path = sys.path[:]
    sys.path.insert(0, BASE_DIR)

    for mod_name in ['integrity_check']:
        if mod_name in sys.modules:
            del sys.modules[mod_name]

    try:
        import integrity_check

        # Calculer l'empreinte de la cle du module d'integrite.
        module_fp = _hmac.new(
            guard_key, integrity_check._INTEGRITY_KEY, _hl.sha256,
        ).hexdigest()

        # Signer
        sig = _hmac.new(guard_key, module_fp.encode(), _hl.sha256).hexdigest()

        guard_data = {'h': module_fp, 's': sig}

        guard_path = os.path.join(OUTPUT_DIR, '.guard.dat')
        with open(guard_path, 'w', encoding='utf-8') as f:
            json.dump(guard_data, f)

        print(f"  [OK] Fichier de garde genere : .guard.dat")
        print(f"  [OK] Empreinte du module d'integrite enregistree")

    except Exception as e:
        print(f"  [ERREUR] Impossible de generer le fichier de garde : {e}")
    finally:
        sys.path[:] = _saved_path


def synchroniser_version_installateur():
    """
    Recopie APP_VERSION dans installer_myschool.iss.

    Le numero vit a un seul endroit, ecole_moderne/version.py : c'est celui
    que l'application compare a la version publiee sur le serveur. Si
    l'installateur en portait un autre, un poste installerait une mise a jour
    puis continuerait a la reclamer indefiniment, chaque demarrage relancant
    le meme installateur.
    """
    step('Numero de version')

    sys.path.insert(0, BASE_DIR)
    from ecole_moderne.version import APP_VERSION

    chemin = os.path.join(BASE_DIR, 'installer_myschool.iss')
    if not os.path.exists(chemin):
        print('  [INFO] installer_myschool.iss absent, etape ignoree')
        return APP_VERSION

    with io.open(chemin, encoding='utf-8-sig', newline='') as fichier:
        contenu = fichier.read()

    motif = re.compile(r'^#define MyAppVersion "[^"]*"', re.MULTILINE)
    if not motif.search(contenu):
        raise SystemExit(
            "  [ERREUR] '#define MyAppVersion' introuvable dans "
            'installer_myschool.iss : le numero de version ne peut pas etre '
            'synchronise.'
        )

    nouveau = motif.sub(f'#define MyAppVersion "{APP_VERSION}"', contenu, count=1)
    if nouveau != contenu:
        with io.open(chemin, 'w', encoding='utf-8-sig', newline='') as fichier:
            fichier.write(nouveau)
        print(f'  [OK] installer_myschool.iss aligne sur la version {APP_VERSION}')
    else:
        print(f'  [OK] Version {APP_VERSION}')
    return APP_VERSION


def empreinte_installateur(version):
    """
    Affiche l'empreinte SHA-256 de l'installateur, si Inno Setup l'a deja produit.

    C'est la valeur a coller dans l'administration pour publier la version :
    les postes refusent d'installer un fichier dont l'empreinte ne correspond
    pas. La calculer ici evite d'aller la chercher a la main, etape ou une
    erreur de copie bloquerait toute la diffusion.
    """
    chemin = os.path.join(
        BASE_DIR, 'Output', f'MySchoolGN_Setup_v{version}_Generic.exe',
    )
    if not os.path.exists(chemin):
        print('')
        print("  Apres la compilation Inno Setup, obtenez l'empreinte a publier par :")
        print("    python build_exe.py --empreinte")
        return None

    # Un installateur portant le bon nom peut dater d'une compilation
    # precedente. Publier son empreinte diffuserait l'ancien code sous le
    # numero de la nouvelle version, et le probleme serait invisible : le
    # fichier s'installe, son empreinte correspond, seul le contenu est
    # perime. On refuse donc de proposer une empreinte plus ancienne que
    # l'executable qui vient d'etre construit.
    executable = os.path.join(OUTPUT_DIR, 'MySchoolGN.exe')
    if os.path.exists(executable) and os.path.getmtime(chemin) < os.path.getmtime(executable):
        print('')
        print('  [ATTENTION] L\'installateur trouve est anterieur a cette compilation.')
        print(f'              {chemin}')
        print("              Recompilez-le avec Inno Setup, sinon l'empreinte publiee")
        print('              correspondrait a une version perimee du code.')
        return None

    condensat = hashlib.sha256()
    with open(chemin, 'rb') as fichier:
        for bloc in iter(lambda: fichier.read(256 * 1024), b''):
            condensat.update(bloc)
    empreinte = condensat.hexdigest()
    taille = os.path.getsize(chemin)

    print('')
    print("  A publier dans Administration > Versions de l'application :")
    print(f'    Version        : {version}')
    print(f'    SHA-256        : {empreinte}')
    print(f'    Taille (octets): {taille}')
    return empreinte


def main():
    print("")
    print("*" * 60)
    print("  MySchoolGN - Compilation en .exe")
    print("  AVEC PROTECTION ANTI-MODIFICATION")
    print("*" * 60)

    os.chdir(BASE_DIR)

    version = synchroniser_version_installateur()
    check_prereqs()
    collect_static()
    run_pyinstaller()
    copy_extra_files()
    verify_static_images()
    copy_gtk_dlls()
    create_launcher_bat()
    create_stop_bat()
    generate_guard_file()
    generate_integrity_manifest()
    protect_source_files()
    compiler_installateur()
    show_summary()
    empreinte_installateur(version)


if __name__ == '__main__':
    # `--empreinte` seul : l'installateur Inno Setup se compile apres ce
    # script, donc son empreinte n'existe pas encore a la fin de la
    # compilation. Ce raccourci evite de tout relancer pour l'obtenir.
    if '--empreinte' in sys.argv:
        sys.path.insert(0, BASE_DIR)
        from ecole_moderne.version import APP_VERSION
        empreinte_installateur(APP_VERSION)
    else:
        main()
