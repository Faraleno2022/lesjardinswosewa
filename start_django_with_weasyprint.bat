@echo off
echo Démarrage de Django avec WeasyPrint...

REM Configuration de l'environnement pour WeasyPrint
set PATH=%PATH%;C:\msys64\mingw64\bin;C:\msys64\usr\bin
set GDK_PIXBUF_MODULE_FILE=C:\msys64\mingw64\lib\gdk-pixbuf-2.0\2.10.0\loaders.cache
set XDG_DATA_DIRS=C:\msys64\mingw64\share

REM Démarrage du serveur Django
echo Lancement du serveur Django...
python manage.py runserver
