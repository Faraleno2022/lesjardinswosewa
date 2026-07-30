@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================================
echo   MySchool - Installation
echo   Gestion Scolaire Hors-Ligne
echo ============================================================
echo.

REM --- Repertoire d'installation ---
set "INSTALL_DIR=C:\MySchool"

echo Le programme sera installe dans: %INSTALL_DIR%
echo.
set /p CONFIRM="Continuer l'installation? (O/N): "
if /i not "%CONFIRM%"=="O" (
    echo Installation annulee.
    pause
    exit /b 0
)

REM --- Creer le repertoire d'installation ---
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo Dossier cree: %INSTALL_DIR%
)

REM --- Creer le repertoire de donnees (preserve lors des mises a jour) ---
if not exist "%INSTALL_DIR%\data" (
    mkdir "%INSTALL_DIR%\data"
    echo Dossier donnees cree: %INSTALL_DIR%\data
)
if not exist "%INSTALL_DIR%\data\media" mkdir "%INSTALL_DIR%\data\media"
if not exist "%INSTALL_DIR%\data\logs" mkdir "%INSTALL_DIR%\data\logs"

REM --- Copier les fichiers de l'application ---
echo.
echo Copie des fichiers de l'application...
xcopy /E /I /Y "%~dp0*" "%INSTALL_DIR%\" /EXCLUDE:%~dp0exclude_copy.txt
echo Copie terminee.

REM --- Creer le raccourci sur le bureau ---
echo.
echo Creation du raccourci sur le bureau...
set "SHORTCUT=%USERPROFILE%\Desktop\MySchool.lnk"
set "VBS_SCRIPT=%TEMP%\create_shortcut_myschool.vbs"

(
echo Set oWS = WScript.CreateObject^("WScript.Shell"^)
echo sLinkFile = "%SHORTCUT%"
echo Set oLink = oWS.CreateShortcut^(sLinkFile^)
echo oLink.TargetPath = "%INSTALL_DIR%\MySchool.exe"
echo oLink.WorkingDirectory = "%INSTALL_DIR%"
echo oLink.Description = "MySchool - Gestion Scolaire"
echo oLink.IconLocation = "%INSTALL_DIR%\myschool.ico"
echo oLink.Save
) > "%VBS_SCRIPT%"

cscript //nologo "%VBS_SCRIPT%"
del "%VBS_SCRIPT%" 2>nul

if exist "%SHORTCUT%" (
    echo Raccourci cree sur le bureau: MySchool
) else (
    echo ATTENTION: Impossible de creer le raccourci automatiquement.
    echo Creez manuellement un raccourci vers: %INSTALL_DIR%\MySchool.exe
)

REM --- Configuration initiale de la base de donnees ---
echo.
echo Configuration initiale de la base de donnees...
cd /d "%INSTALL_DIR%"
"%INSTALL_DIR%\MySchool.exe" --setup-only
echo.

echo ============================================================
echo   Installation terminee!
echo.
echo   Pour lancer MySchool:
echo   - Double-cliquez sur le raccourci "MySchool" sur le bureau
echo   - Ou executez: %INSTALL_DIR%\MySchool.exe
echo.
echo   Compte par defaut:
echo     Utilisateur: admin
echo     Mot de passe: admin1234
echo     (Changez-le apres la premiere connexion)
echo ============================================================
pause
