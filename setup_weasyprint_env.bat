@echo off
echo Configuration de l'environnement WeasyPrint...

REM Ajouter les chemins MSYS2 au PATH pour cette session
set PATH=%PATH%;C:\msys64\mingw64\bin;C:\msys64\usr\bin

REM Configurer les variables d'environnement pour GTK
set GDK_PIXBUF_MODULE_FILE=C:\msys64\mingw64\lib\gdk-pixbuf-2.0\2.10.0\loaders.cache
set XDG_DATA_DIRS=C:\msys64\mingw64\share

echo Environnement WeasyPrint configuré!
echo.
echo Pour que les changements soient permanents, exécutez cette commande en tant qu'administrateur:
echo setx PATH "%PATH%;C:\msys64\mingw64\bin;C:\msys64\usr\bin" /M
echo.
echo Lancez maintenant votre serveur Django avec:
echo python manage.py runserver
pause
