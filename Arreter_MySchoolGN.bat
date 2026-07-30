@echo off
:: ============================================================
::  Arreter_MySchoolGN.bat
::  Arrête le serveur MySchoolGN proprement
::  Auteur : GS Hadja Kanfing Dian
:: ============================================================

title Arrêt de MySchoolGN

echo.
echo  ====================================
echo   MySchoolGN - Arrêt du serveur
echo  ====================================
echo.

:: Vérifier si le processus tourne
tasklist /FI "IMAGENAME eq MySchoolGN.exe" 2>NUL | find /I "MySchoolGN.exe" >NUL
if errorlevel 1 (
    echo  MySchoolGN n'est pas en cours d'execution.
    echo.
    pause
    exit /b 0
)

echo  Arrêt de MySchoolGN en cours...
taskkill /F /IM MySchoolGN.exe >NUL 2>&1

if errorlevel 1 (
    echo  ERREUR : Impossible d'arrêter MySchoolGN.
    echo  Essayez de fermer la fenêtre manuellement.
) else (
    echo  MySchoolGN a été arrêté avec succès.
)

echo.
pause
