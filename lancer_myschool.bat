@echo off
chcp 65001 >nul 2>&1
title MySchool - Gestion Scolaire

echo.
echo ========================================================
echo         MySchool - Gestion Scolaire
echo         Version Desktop Hors-Ligne
echo ========================================================
echo.
echo Demarrage en cours, veuillez patienter...
echo.

REM --- Aller dans le repertoire du projet ---
cd /d "%~dp0"

REM --- Lancer le serveur Django ---
python desktop\run_server.py

REM --- Si erreur, afficher un message ---
if errorlevel 1 (
    echo.
    echo ========================================================
    echo   ERREUR: Le serveur n'a pas pu demarrer.
    echo   Verifiez que Python est installe correctement.
    echo ========================================================
    echo.
    pause
)
