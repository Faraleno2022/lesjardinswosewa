@echo off
REM ===================================================================
REM  MySchoolGN - Sauvegarde immediate (base de donnees + medias)
REM
REM  Depose une archive sur chaque destination : dossier local,
REM  dossier cloud synchronise, cle USB ou disque externe branche.
REM  Fonctionne application fermee, et meme licence expiree.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo  Sauvegarde de MySchoolGN en cours...
echo.

if exist "MySchoolGN.exe" (
    MySchoolGN.exe --sauvegarder
) else if exist "venv\Scripts\python.exe" (
    venv\Scripts\python.exe manage.py sauvegarder
) else (
    python manage.py sauvegarder
)

set CODE=%ERRORLEVEL%
echo.
if "%CODE%"=="0" (
    echo  Sauvegarde terminee. Detail : logs\sauvegarde.log
) else (
    echo  ECHEC de la sauvegarde ^(code %CODE%^). Voir logs\sauvegarde.log
)
echo.
pause
endlocal
