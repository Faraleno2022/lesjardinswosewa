@echo off
title MySchoolGN - Installation
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo    MySchoolGN - Installation Offline
echo    Systeme de Gestion Scolaire
echo ============================================================
echo.

:: Verifier les privileges administrateur
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ATTENTION] Execution sans privileges administrateur.
    echo              Certaines fonctions peuvent ne pas fonctionner.
    echo              Pour une installation complete, executez en tant qu'administrateur.
    echo.
)

:: Demander le repertoire d'installation
set "INSTALL_DIR=C:\MySchoolGN"
echo Repertoire d'installation par defaut: %INSTALL_DIR%
set /p "CUSTOM_DIR=Appuyez sur Entree pour accepter ou saisissez un autre chemin: "
if not "%CUSTOM_DIR%"=="" set "INSTALL_DIR=%CUSTOM_DIR%"

echo.
echo Installation dans: %INSTALL_DIR%
echo.

:: Creer le repertoire d'installation
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    if errorlevel 1 (
        echo [ERREUR] Impossible de creer le repertoire %INSTALL_DIR%
        echo          Verifiez vos permissions.
        pause
        exit /b 1
    )
)

:: Copier les fichiers
echo [1/5] Copie des fichiers de l'application...
xcopy /s /e /y /q "%~dp0dist\MySchoolGN\*" "%INSTALL_DIR%\" >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] La copie des fichiers a echoue.
    echo          Assurez-vous que le dossier dist\MySchoolGN existe.
    echo          Lancez d'abord la compilation: python build_exe.py
    pause
    exit /b 1
)
echo        [OK] Fichiers copies.

:: Creer les sous-dossiers necessaires
echo [2/5] Creation des dossiers de donnees...
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
if not exist "%INSTALL_DIR%\media" mkdir "%INSTALL_DIR%\media"
if not exist "%INSTALL_DIR%\media\photos_eleves" mkdir "%INSTALL_DIR%\media\photos_eleves"
if not exist "%INSTALL_DIR%\media\logos_ecoles" mkdir "%INSTALL_DIR%\media\logos_ecoles"
if not exist "%INSTALL_DIR%\backups" mkdir "%INSTALL_DIR%\backups"
echo        [OK] Dossiers crees.

:: Creer le raccourci sur le Bureau
echo [3/5] Creation du raccourci sur le Bureau...
set "DESKTOP=%USERPROFILE%\Desktop"
set "SHORTCUT=%DESKTOP%\MySchoolGN.lnk"

:: Utiliser PowerShell pour creer le raccourci
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = '%INSTALL_DIR%\Demarrer_MySchoolGN.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'MySchoolGN - Systeme de Gestion Scolaire'; $s.Save()" >nul 2>&1
if exist "%SHORTCUT%" (
    echo        [OK] Raccourci cree sur le Bureau.
) else (
    echo        [AVERTISSEMENT] Impossible de creer le raccourci.
)

:: Creer l'entree dans le menu Demarrer
echo [4/5] Creation de l'entree dans le menu Demarrer...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\MySchoolGN"
if not exist "%STARTMENU%" mkdir "%STARTMENU%"
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTMENU%\MySchoolGN.lnk'); $s.TargetPath = '%INSTALL_DIR%\Demarrer_MySchoolGN.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'MySchoolGN - Systeme de Gestion Scolaire'; $s.Save()" >nul 2>&1
powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%STARTMENU%\Desinstaller MySchoolGN.lnk'); $s.TargetPath = '%INSTALL_DIR%\desinstaller.bat'; $s.WorkingDirectory = '%INSTALL_DIR%'; $s.Description = 'Desinstaller MySchoolGN'; $s.Save()" >nul 2>&1
echo        [OK] Menu Demarrer configure.

:: Enregistrer les informations de desinstallation dans le registre
echo [5/5] Enregistrement dans le systeme...
set "REG_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MySchoolGN"
reg add "%REG_KEY%" /v "DisplayName" /t REG_SZ /d "MySchoolGN - Systeme de Gestion Scolaire" /f >nul 2>&1
reg add "%REG_KEY%" /v "UninstallString" /t REG_SZ /d "\"%INSTALL_DIR%\desinstaller.bat\"" /f >nul 2>&1
reg add "%REG_KEY%" /v "InstallLocation" /t REG_SZ /d "%INSTALL_DIR%" /f >nul 2>&1
reg add "%REG_KEY%" /v "Publisher" /t REG_SZ /d "MySchoolGN" /f >nul 2>&1
reg add "%REG_KEY%" /v "DisplayVersion" /t REG_SZ /d "1.0.0" /f >nul 2>&1
reg add "%REG_KEY%" /v "NoModify" /t REG_DWORD /d 1 /f >nul 2>&1
reg add "%REG_KEY%" /v "NoRepair" /t REG_DWORD /d 1 /f >nul 2>&1
echo        [OK] Application enregistree.

:: Copier le script de desinstallation
copy /y "%~dp0desinstaller.bat" "%INSTALL_DIR%\desinstaller.bat" >nul 2>&1

:: Sauvegarder le chemin d'installation pour la desinstallation
echo %INSTALL_DIR%> "%INSTALL_DIR%\install_path.txt"

echo.
echo ============================================================
echo    INSTALLATION TERMINEE AVEC SUCCES!
echo ============================================================
echo.
echo    Repertoire: %INSTALL_DIR%
echo    Raccourci:  Bureau (MySchoolGN)
echo.
echo    Pour demarrer l'application:
echo      - Double-cliquez sur le raccourci 'MySchoolGN' sur le Bureau
echo      - Ou lancez '%INSTALL_DIR%\Demarrer_MySchoolGN.bat'
echo.
echo    Identifiants par defaut:
echo      Utilisateur: admin
echo      Mot de passe: admin1234
echo.
echo    L'application s'ouvre dans votre navigateur web sur:
echo      http://127.0.0.1:8000
echo.
echo ============================================================
echo.

set /p "LAUNCH=Voulez-vous demarrer MySchoolGN maintenant? (O/N): "
if /i "%LAUNCH%"=="O" (
    start "" "%INSTALL_DIR%\Demarrer_MySchoolGN.bat"
)

pause
