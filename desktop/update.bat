@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================================
echo   MySchool - Mise a Jour
echo ============================================================
echo.

set "INSTALL_DIR=C:\MySchool"

if not exist "%INSTALL_DIR%" (
    echo MySchool n'est pas installe. Utilisez installer.bat d'abord.
    pause
    exit /b 1
)

if not exist "%INSTALL_DIR%\data\db.sqlite3" (
    echo ATTENTION: Aucune base de donnees trouvee.
    echo Utilisez installer.bat pour une installation complete.
    pause
    exit /b 1
)

echo La mise a jour va:
echo   - Remplacer les fichiers de l'application
echo   - CONSERVER la base de donnees et les fichiers media
echo   - Appliquer les nouvelles migrations
echo.
set /p CONFIRM="Continuer la mise a jour? (O/N): "
if /i not "%CONFIRM%"=="O" (
    echo Mise a jour annulee.
    pause
    exit /b 0
)

REM --- Sauvegarde de la base de donnees ---
echo.
echo Sauvegarde de la base de donnees...
set "BACKUP_DATE=%DATE:~6,4%%DATE:~3,2%%DATE:~0,2%"
copy "%INSTALL_DIR%\data\db.sqlite3" "%INSTALL_DIR%\data\db.sqlite3.backup.%BACKUP_DATE%" >nul 2>&1
if exist "%INSTALL_DIR%\data\db.sqlite3.backup.%BACKUP_DATE%" (
    echo Sauvegarde effectuee: db.sqlite3.backup.%BACKUP_DATE%
) else (
    echo Note: Format de date non standard, sauvegarde sous nom generique...
    copy "%INSTALL_DIR%\data\db.sqlite3" "%INSTALL_DIR%\data\db.sqlite3.backup" >nul 2>&1
)

REM --- Supprimer les anciens fichiers application ---
echo Suppression des anciens fichiers...
for %%f in ("%INSTALL_DIR%\*.exe" "%INSTALL_DIR%\*.dll" "%INSTALL_DIR%\*.ico") do (
    if exist "%%f" del /f /q "%%f"
)
if exist "%INSTALL_DIR%\_internal" rmdir /s /q "%INSTALL_DIR%\_internal"
if exist "%INSTALL_DIR%\static" rmdir /s /q "%INSTALL_DIR%\static"
if exist "%INSTALL_DIR%\staticfiles" rmdir /s /q "%INSTALL_DIR%\staticfiles"
if exist "%INSTALL_DIR%\templates" rmdir /s /q "%INSTALL_DIR%\templates"

REM --- Copier les nouveaux fichiers ---
echo Copie des nouveaux fichiers...
xcopy /E /I /Y "%~dp0*" "%INSTALL_DIR%\" /EXCLUDE:%~dp0exclude_copy.txt

REM --- Appliquer les nouvelles migrations ---
echo.
echo Application des migrations...
cd /d "%INSTALL_DIR%"
"%INSTALL_DIR%\MySchool.exe" --setup-only

echo.
echo ============================================================
echo   Mise a jour terminee!
echo   Lancez MySchool normalement.
echo ============================================================
pause
