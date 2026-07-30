#!/usr/bin/env bash
set -euo pipefail

# PythonAnywhere deploy helper
# Usage examples:
#   PA_DOMAIN="<YourUser>.pythonanywhere.com" bash scripts/deploy_pa.sh
#   APP_DIR="$HOME/GS_hadja_kanfing_dian-" PA_DOMAIN="<YourUser>.pythonanywhere.com" bash scripts/deploy_pa.sh
#   USE_VENV=1 VENV_NAME="gs-hadja-env" PA_DOMAIN="<YourUser>.pythonanywhere.com" bash scripts/deploy_pa.sh

APP_DIR="${APP_DIR:-$HOME/GS_hadja_kanfing_dian-}"
PA_DOMAIN="${PA_DOMAIN:-<YourUsername>.pythonanywhere.com}"
USE_VENV="${USE_VENV:-0}"
VENV_NAME="${VENV_NAME:-gs-hadja-env}"

 echo "==> App directory: $APP_DIR"
 echo "==> Domain:        $PA_DOMAIN"
 echo "==> Use venv:      $USE_VENV (${VENV_NAME})"

 cd "$APP_DIR"

 echo "\n==> Pulling latest code (origin/main)"
 git pull --rebase origin main

 if [[ "$USE_VENV" == "1" ]]; then
   echo "\n==> Activating virtualenv: $VENV_NAME"
   if command -v workon >/dev/null 2>&1; then
     workon "$VENV_NAME" || echo "Virtualenv '$VENV_NAME' not found, continuing without venv"
   else
     echo "'workon' command not available. Skipping venv activation."
   fi
 fi

 echo "\n==> Installing requirements"
 pip install -r requirements.txt --user

 echo "\n==> Applying migrations"
 python manage.py migrate --noinput

 echo "\n==> Collecting static files"
 python manage.py collectstatic --noinput

 echo "\n==> Reloading web app"
 if command -v pa_reload_webapp.py >/dev/null 2>&1; then
   pa_reload_webapp.py "$PA_DOMAIN" || echo "Reload helper failed; reload manually from Web dashboard."
 else
   echo "Reload helper not found; please reload from the PythonAnywhere Web dashboard."
 fi

 echo "\n==> Deployment finished."
