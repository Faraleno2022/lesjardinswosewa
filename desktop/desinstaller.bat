@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion

echo ============================================================
echo   MySchool - Desinstallation
echo ============================================================
echo.

set "INSTALL_DIR=C:\MySchool"

if not exist "%INSTALL_DIR%" (
    echo MySchool n'est pas installe dans %INSTALL_DIR%.
    pause
    exit /b 0
)

echo ATTENTION: Les fichiers de l'application seront supprimes.
echo La base de donnees et les fichiers media seront CONSERVES
echo dans: %INSTALL_DIR%\data\
echo.
set /p CONFIRM="Confirmer la desinstallation? (O/N): "
if /i not "%CONFIRM%"=="O" (
    echo Desinstallation annulee.
    pause
    exit /b 0
)

REM --- Supprimer le raccourci bureau ---
echo Suppression du raccourci...
if exist "%USERPROFILE%\Desktop\MySchool.lnk" (
    del "%USERPROFILE%\Desktop\MySchool.lnk"
    echo Raccourci supprime.
)

REM --- Supprimer les fichiers application (PAS les donnees) ---
echo Suppression des fichiers de l'application...

REM Supprimer les executables et DLLs
for %%f in ("%INSTALL_DIR%\*.exe" "%INSTALL_DIR%\*.dll" "%INSTALL_DIR%\*.ico" "%INSTALL_DIR%\*.bat" "%INSTALL_DIR%\*.txt") do (
    if exist "%%f" del /f /q "%%f"
)

REM Supprimer le repertoire _internal (deps PyInstaller)
if exist "%INSTALL_DIR%\_internal" (
    rmdir /s /q "%INSTALL_DIR%\_internal"
)

REM Supprimer les fichiers statiques et templates (fichiers app, pas donnees)
if exist "%INSTALL_DIR%\static" rmdir /s /q "%INSTALL_DIR%\static"
if exist "%INSTALL_DIR%\staticfiles" rmdir /s /q "%INSTALL_DIR%\staticfiles"
if exist "%INSTALL_DIR%\templates" rmdir /s /q "%INSTALL_DIR%\templates"

echo.
echo ============================================================
echo   Desinstallation terminee!
echo.
echo   Les donnees ont ete conservees dans:
echo   %INSTALL_DIR%\data\
echo.
echo   Pour supprimer definitivement toutes les donnees:
echo   Supprimez manuellement le dossier %INSTALL_DIR%
echo ============================================================
pause
