@echo off
REM ===================================================================
REM  MySchoolGN - Installe la sauvegarde nocturne automatique
REM
REM  A executer UNE SEULE FOIS par poste, en tant qu'administrateur
REM  (clic droit > Executer en tant qu'administrateur).
REM
REM  Cree une tache Windows qui sauvegarde chaque nuit a 20h00, meme si
REM  MySchoolGN est ferme. L'application, quand elle tourne, sauvegarde
REM  aussi d'elle-meme toutes les 6 heures : les deux se completent.
REM ===================================================================
setlocal
cd /d "%~dp0"

set TACHE=MySchoolGN - Sauvegarde quotidienne
set HEURE=20:00

net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ATTENTION : lancez ce fichier en tant qu'administrateur.
    echo  Clic droit sur Planifier_Sauvegarde.bat ^> Executer en tant qu'administrateur
    echo.
    pause
    exit /b 1
)

if exist "%~dp0MySchoolGN.exe" (
    set CIBLE="%~dp0MySchoolGN.exe" --sauvegarder
) else (
    set CIBLE="%~dp0Sauvegarder_MySchoolGN.bat"
)

echo.
echo  Installation de la tache planifiee...
echo    Tache  : %TACHE%
echo    Heure  : %HEURE% chaque jour
echo    Cible  : %CIBLE%
echo.

schtasks /Create /TN "%TACHE%" /TR "%CIBLE%" /SC DAILY /ST %HEURE% /RL HIGHEST /F
if errorlevel 1 (
    echo.
    echo  ECHEC de la creation de la tache.
    pause
    exit /b 1
)

REM Rattrapage : si le poste etait eteint a l'heure prevue, la tache
REM s'execute au demarrage suivant. Sans cela, une nuit d'extinction
REM signifie une journee sans sauvegarde nocturne.
schtasks /Change /TN "%TACHE%" /ENABLE >nul 2>&1

echo.
echo  Tache installee. Verification :
schtasks /Query /TN "%TACHE%" /FO LIST | findstr /I "TaskName Next Status"
echo.
echo  Pour tester tout de suite : schtasks /Run /TN "%TACHE%"
echo  Pour la retirer          : schtasks /Delete /TN "%TACHE%" /F
echo.
pause
endlocal
