# -*- mode: python ; coding: utf-8 -*-
"""Construction PyInstaller de l'application Windows MySchoolGN."""

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


PROJECT_DIR = SPECPATH
PROJECT_PACKAGES = [
    'ecole_moderne',
    'eleves',
    'paiements',
    'depenses',
    'salaires',
    'utilisateurs',
    'rapports',
    'administration',
    'bus',
    'notes',
    'presence',
    'abonnements',
    'chatbot',
    'synchronisation',
]

datas = []
for source, destination in [
    ('templates', 'templates'),
    ('static', 'static'),
    ('staticfiles', 'staticfiles'),
]:
    path = os.path.join(PROJECT_DIR, source)
    if os.path.isdir(path):
        datas.append((path, destination))

hiddenimports = [
    'django.core.management.commands.runserver',
    'django.core.management.commands.migrate',
    'django.contrib.staticfiles.management.commands.collectstatic',
    'django.db.backends.sqlite3',
    'license_manager',
    'integrity_check',
    'load_env',
]

for package in PROJECT_PACKAGES:
    hiddenimports += collect_submodules(package)
    datas += collect_data_files(package, includes=['templates/**/*'])

for package in ['axes', 'whitenoise', 'reportlab', 'openpyxl', 'weasyprint', 'PIL']:
    hiddenimports += collect_submodules(package)

for distribution in ['Django', 'django-axes', 'whitenoise', 'weasyprint']:
    try:
        datas += copy_metadata(distribution)
    except Exception:
        pass

icon_path = os.path.join(PROJECT_DIR, 'myschool.ico')
icon = icon_path if os.path.exists(icon_path) else None

a = Analysis(
    [os.path.join(PROJECT_DIR, 'run_server.py')],
    pathex=[PROJECT_DIR],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['MySQLdb', 'mysqlclient', 'PyMySQL'],
    noarchive=False,
    optimize=0,
)

# Le hook Django detecte la base SQLite du poste de compilation et l'ajoute
# automatiquement aux donnees PyInstaller. Un installateur generique ne doit
# jamais embarquer cette base, meme dans le dossier interne ou elle serait
# normalement inutilisee.
a.datas = [
    entry for entry in a.datas
    if os.path.basename(entry[0]).lower() != 'db.sqlite3'
]

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MySchoolGN',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MySchoolGN',
)
