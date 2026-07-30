@echo off
title MySchoolGN - Desinstallation
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo.
echo ============================================================
echo    MySchoolGN - Desinstallation
echo    Systeme de Gestion Scolaire
echo ============================================================
echo.

:: Determiner le repertoire d'installation
set "INSTALL_DIR=%~dp0"
:: Retirer le \ final
set "INSTALL_DIR=%INSTALL_DIR:~0,-1%"

echo Repertoire d'installation detecte: %INSTALL_DIR%
echo.

:: Confirmation
set /p "CONFIRM=Voulez-vous vraiment desinstaller MySchoolGN? (O/N): "
if /i not "%CONFIRM%"=="O" (
    echo Desinstallation annulee.
    pause
    exit /b 0
)

echo.

:: Etape 1: Arreter le serveur s'il est en cours
echo [1/6] Arret du serveur MySchoolGN...
taskkill /F /IM MySchoolGN.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo        [OK] Serveur arrete.
    timeout /t 2 >nul
) else (
    echo        [OK] Le serveur n'etait pas en cours d'execution.
)

:: Etape 2: Proposer la sauvegarde de la base de donnees
echo [2/6] Sauvegarde des donnees...
if exist "%INSTALL_DIR%\db.sqlite3" (
    set /p "BACKUP=Voulez-vous sauvegarder votre base de donnees avant la suppression? (O/N): "
    if /i "!BACKUP!"=="O" (
        set "BACKUP_DIR=%USERPROFILE%\Documents\MySchoolGN_Backup"
        if not exist "!BACKUP_DIR!" mkdir "!BACKUP_DIR!"
        copy /y "%INSTALL_DIR%\db.sqlite3" "!BACKUP_DIR!\db_backup_%date:~-4%%date:~3,2%%date:~0,2%.sqlite3" >nul 2>&1
        if not errorlevel 1 (
            echo        [OK] Base de donnees sauvegardee dans: !BACKUP_DIR!
        ) else (
            echo        [AVERTISSEMENT] Erreur lors de la sauvegarde.
            copy /y "%INSTALL_DIR%\db.sqlite3" "%USERPROFILE%\Desktop\myschool_backup.sqlite3" >nul 2>&1
            echo        [OK] Sauvegarde alternative sur le Bureau.
        )
    ) else (
        echo        [INFO] Aucune sauvegarde effectuee.
    )
) else (
    echo        [INFO] Aucune base de donnees trouvee.
)

:: Etape 3: Supprimer le raccourci du Bureau
echo [3/6] Suppression du raccourci Bureau...
set "DESKTOP=%USERPROFILE%\Desktop"
if exist "%DESKTOP%\MySchoolGN.lnk" (
    del /f "%DESKTOP%\MySchoolGN.lnk" >nul 2>&1
    echo        [OK] Raccourci Bureau supprime.
) else (
    echo        [OK] Aucun raccourci Bureau trouve.
)

:: Etape 4: Supprimer l'entree du menu Demarrer
echo [4/6] Suppression du menu Demarrer...
set "STARTMENU=%APPDATA%\Microsoft\Windows\Start Menu\Programs\MySchoolGN"
if exist "%STARTMENU%" (
    rmdir /s /q "%STARTMENU%" >nul 2>&1
    echo        [OK] Menu Demarrer nettoye.
) else (
    echo        [OK] Aucune entree Menu Demarrer trouvee.
)

:: Etape 5: Supprimer l'entree du registre
echo [5/6] Nettoyage du registre...
set "REG_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\MySchoolGN"
reg query "%REG_KEY%" >nul 2>&1
if %errorlevel% equ 0 (
    reg delete "%REG_KEY%" /f >nul 2>&1
    echo        [OK] Entree du registre supprimee.
) else (
    echo        [OK] Aucune entree du registre trouvee.
)

:: Etape 6: Supprimer les fichiers de l'application
echo [6/6] Suppression des fichiers...
echo.
echo        ATTENTION: Le dossier suivant va etre supprime:
echo        %INSTALL_DIR%
echo.
set /p "CONFIRM_DEL=Confirmer la suppression des fichiers? (O/N): "
if /i "%CONFIRM_DEL%"=="O" (
    :: Se deplacer en dehors du repertoire avant de le supprimer
    cd /d "%USERPROFILE%"

    :: Supprimer le contenu du repertoire
    rmdir /s /q "%INSTALL_DIR%" >nul 2>&1

    if not exist "%INSTALL_DIR%" (
        echo        [OK] Fichiers supprimes avec succes.
    ) else (
        echo        [AVERTISSEMENT] Certains fichiers n'ont pas pu etre supprimes.
        echo        Vous pouvez supprimer manuellement: %INSTALL_DIR%
    )
) else (
    echo        [INFO] Les fichiers ont ete conserves dans: %INSTALL_DIR%
)

echo.
echo ============================================================
echo    DESINSTALLATION TERMINEE
echo ============================================================
echo.
echo    MySchoolGN a ete desinstalle de votre ordinateur.
echo.
if defined BACKUP_DIR (
    echo    Sauvegarde de vos donnees: !BACKUP_DIR!
)
echo.
echo ============================================================
echo.

pause
