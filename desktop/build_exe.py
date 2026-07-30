"""
Script de build PyInstaller pour MySchool Desktop.
Usage: python desktop/build_exe.py
"""
import os
import sys
import shutil
from pathlib import Path

# Répertoire racine du projet
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def convert_logo_to_ico():
    """Convertit le logo PNG en ICO pour l'exécutable et le raccourci."""
    from PIL import Image

    logo_png = PROJECT_ROOT / 'static' / 'logos' / 'logo.png'
    ico_path = PROJECT_ROOT / 'desktop' / 'myschool.ico'

    if not logo_png.exists():
        print(f"[BUILD] ATTENTION: Logo introuvable: {logo_png}")
        return None

    img = Image.open(logo_png)
    # Convertir en RGBA si nécessaire
    if img.mode != 'RGBA':
        img = img.convert('RGBA')

    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(str(ico_path), format='ICO', sizes=icon_sizes)
    print(f"[BUILD] Icône créée: {ico_path}")
    return str(ico_path)


def run_collectstatic():
    """Exécute collectstatic avant le build."""
    os.environ['DJANGO_SETTINGS_MODULE'] = 'desktop.settings_desktop'
    os.environ['MYSCHOOL_DESKTOP'] = '1'
    sys.path.insert(0, str(PROJECT_ROOT))

    import django
    django.setup()
    from django.core.management import call_command

    print("[BUILD] Collecte des fichiers statiques...")
    call_command('collectstatic', '--noinput', verbosity=1)
    print("[BUILD] Fichiers statiques collectés.")


def build():
    """Lance le build PyInstaller."""
    import PyInstaller.__main__

    print("=" * 60)
    print("  MySchool — Build Desktop")
    print("=" * 60)

    # 1. Convertir le logo en icône
    ico_path = convert_logo_to_ico()

    # 2. Collecter les fichiers statiques
    run_collectstatic()

    # 3. Préparer les données à inclure
    django_apps = [
        'eleves', 'paiements', 'depenses', 'salaires', 'utilisateurs',
        'rapports', 'administration', 'bus', 'notes', 'abonnements',
        'chatbot', 'ecole_moderne', 'desktop',
    ]

    datas = [
        # Templates globaux
        (str(PROJECT_ROOT / 'templates'), 'templates'),
        # Fichiers statiques
        (str(PROJECT_ROOT / 'static'), 'static'),
        # Fichiers statiques collectés
        (str(PROJECT_ROOT / 'staticfiles'), 'staticfiles'),
        # load_env.py (nécessaire pour manage.py)
        (str(PROJECT_ROOT / 'load_env.py'), '.'),
    ]

    # Ajouter les migrations et templatetags de chaque app
    for app in django_apps:
        app_dir = PROJECT_ROOT / app
        if not app_dir.exists():
            continue
        if (app_dir / 'migrations').exists():
            datas.append((str(app_dir / 'migrations'), f'{app}/migrations'))
        if (app_dir / 'templates').exists():
            datas.append((str(app_dir / 'templates'), f'{app}/templates'))
        if (app_dir / 'templatetags').exists():
            datas.append((str(app_dir / 'templatetags'), f'{app}/templatetags'))

    # 4. Imports cachés
    hidden_imports = [
        # Django core
        'django.contrib.admin', 'django.contrib.auth',
        'django.contrib.contenttypes', 'django.contrib.sessions',
        'django.contrib.messages', 'django.contrib.staticfiles',
        'django.contrib.humanize',
        'django.core.management.commands.runserver',
        'django.core.management.commands.migrate',
        'django.core.management.commands.collectstatic',
        'django.db.backends.sqlite3',
        # Projet
        'ecole_moderne', 'ecole_moderne.settings', 'ecole_moderne.urls',
        'ecole_moderne.wsgi',
        'desktop', 'desktop.settings_desktop',
        'load_env',
    ]

    # Ajouter chaque app et ses sous-modules principaux
    for app in django_apps:
        hidden_imports.append(app)
        for sub in ['models', 'views', 'urls', 'admin', 'apps', 'forms']:
            module = f'{app}.{sub}'
            module_path = PROJECT_ROOT / app / f'{sub}.py'
            if module_path.exists():
                hidden_imports.append(module)

    # Modules views supplémentaires
    extra_views = [
        'notes.views_import', 'notes.views_maternelle',
        'notes.bulletin_intelligent', 'notes.bulletin_public',
        'notes.export_classement', 'notes.export_resultats',
        'notes.export_notes_complet', 'notes.export_statistiques_pdf',
        'notes.certificats', 'notes.tableau_honneur',
        'notes.calculs_moyennes', 'notes.utils_rangs',
        'paiements.views_rappels',
        'utilisateurs.security_views', 'utilisateurs.permission_views',
        'utilisateurs.context_processors', 'utilisateurs.utils',
        'eleves.views_nouvelle_annee',
        'ecole_moderne.decorators', 'ecole_moderne.middleware',
        'ecole_moderne.image_cache_middleware',
        'ecole_moderne.image_optimization_middleware',
    ]
    hidden_imports.extend(extra_views)

    # Templatetags
    templatetags = [
        'eleves.templatetags.static_versioned',
        'notes.templatetags.notes_extras',
        'notes.templatetags.notes_tags',
        'salaires.templatetags.salaire_tags',
    ]
    hidden_imports.extend(templatetags)

    # Bibliothèques tierces
    libs = [
        'reportlab', 'reportlab.lib', 'reportlab.pdfgen',
        'reportlab.platypus', 'reportlab.lib.pagesizes',
        'openpyxl', 'PIL', 'PIL.Image',
        'dateutil', 'python_dateutil',
    ]
    hidden_imports.extend(libs)

    # 5. Arguments PyInstaller
    sep = os.pathsep
    pyinstaller_args = [
        str(PROJECT_ROOT / 'desktop' / 'run_server.py'),
        '--name=MySchool',
        '--onedir',
        f'--distpath={PROJECT_ROOT / "dist"}',
        f'--workpath={PROJECT_ROOT / "build"}',
        f'--specpath={PROJECT_ROOT / "desktop"}',
        '--console',
        '--noconfirm',
    ]

    if ico_path:
        pyinstaller_args.append(f'--icon={ico_path}')

    for src, dst in datas:
        pyinstaller_args.append(f'--add-data={src}{sep}{dst}')

    for imp in hidden_imports:
        pyinstaller_args.append(f'--hidden-import={imp}')

    # Exclure les modules inutiles
    for exc in ['tkinter', 'test', 'unittest', 'mysqlclient', 'PyMySQL']:
        pyinstaller_args.append(f'--exclude-module={exc}')

    # 6. Build
    print("[BUILD] Lancement de PyInstaller...")
    PyInstaller.__main__.run(pyinstaller_args)

    # 7. Post-build : copier l'icône et les scripts batch
    dist_dir = PROJECT_ROOT / 'dist' / 'MySchool'
    if dist_dir.exists():
        if ico_path:
            shutil.copy2(ico_path, dist_dir / 'myschool.ico')

        # Copier les scripts d'installation
        for batch_file in ['installer.bat', 'desinstaller.bat', 'update.bat', 'exclude_copy.txt']:
            src = PROJECT_ROOT / 'desktop' / batch_file
            if src.exists():
                shutil.copy2(src, dist_dir / batch_file)

        print()
        print("=" * 60)
        print(f"  Build terminé! Distribution dans:")
        print(f"  {dist_dir}")
        print()
        print("  Pour tester: dist\\MySchool\\MySchool.exe")
        print("=" * 60)
    else:
        print("[BUILD] ERREUR: Le dossier dist/MySchool n'a pas été créé.")


if __name__ == '__main__':
    build()
