#!/usr/bin/env bash
set -Eeuo pipefail

# Déploiement reproductible sur PythonAnywhere.
#
# Exemple :
#   PA_DOMAIN="myschoolgn.pythonanywhere.com" \
#   VENV_DIR="$HOME/.virtualenvs/myschool" \
#   bash scripts/deploy_pa.sh

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
PA_DOMAIN="${PA_DOMAIN:-}"
VENV_DIR="${VENV_DIR:-$HOME/.virtualenvs/myschool}"
ENV_FILE="${ENV_FILE:-$APP_DIR/.env}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
SKIP_RELOAD="${SKIP_RELOAD:-0}"

fail() {
  echo "[ERREUR] $*" >&2
  exit 1
}

on_error() {
  echo "[ERREUR] Déploiement interrompu à la ligne $1. L'application n'a pas été rechargée." >&2
}
trap 'on_error $LINENO' ERR

[[ -n "$PA_DOMAIN" ]] || fail "Définissez PA_DOMAIN avec le domaine PythonAnywhere de l'application web."
[[ "$PA_DOMAIN" != *"<"* ]] || fail "PA_DOMAIN contient encore une valeur d'exemple."
[[ -d "$APP_DIR/.git" ]] || fail "Dépôt Git introuvable dans $APP_DIR."
[[ -f "$ENV_FILE" ]] || fail "Fichier de production introuvable : $ENV_FILE"
[[ -x "$VENV_DIR/bin/python" ]] || fail "Python du virtualenv introuvable : $VENV_DIR/bin/python"

PYTHON="$VENV_DIR/bin/python"

echo "==> Application : $APP_DIR"
echo "==> Branche     : $GIT_REMOTE/$GIT_BRANCH"
echo "==> Virtualenv  : $VENV_DIR"
echo "==> Web app     : $PA_DOMAIN"

cd "$APP_DIR"

if [[ "$SKIP_GIT_PULL" != "1" ]]; then
  echo "==> Synchronisation du code"
  git fetch "$GIT_REMOTE" "$GIT_BRANCH"
  if [[ "$(git branch --show-current)" != "$GIT_BRANCH" ]]; then
    git switch "$GIT_BRANCH"
  fi
  git pull --ff-only "$GIT_REMOTE" "$GIT_BRANCH"
fi

echo "==> Installation des dépendances"
"$PYTHON" -m pip install -r requirements.txt

echo "==> Vérification de la configuration de production"
"$PYTHON" - <<'PY'
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecole_moderne.settings")

import django

django.setup()

from django.conf import settings

errors = []
if settings.DEBUG:
    errors.append("DJANGO_DEBUG doit être false")
if settings.SECRET_KEY == "dev-unsafe-key" or len(settings.SECRET_KEY) < 40:
    errors.append("DJANGO_SECRET_KEY doit être une clé de production forte")
if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.mysql":
    errors.append("la base de production doit utiliser MySQL")
if not settings.DATABASES["default"].get("PASSWORD"):
    errors.append("DJANGO_DB_PASSWORD est manquant")
if not settings.ALLOWED_HOSTS:
    errors.append("DJANGO_ALLOWED_HOSTS est vide")

if errors:
    raise SystemExit("Configuration invalide :\n- " + "\n- ".join(errors))

print("Configuration production valide.")
PY

"$PYTHON" manage.py check --deploy

echo "==> Application des migrations"
"$PYTHON" manage.py migrate --noinput

echo "==> Collecte des fichiers statiques"
"$PYTHON" manage.py collectstatic --noinput

echo "==> Contrôle Django final"
"$PYTHON" manage.py check

if [[ "$SKIP_RELOAD" == "1" ]]; then
  echo "==> Rechargement ignoré (SKIP_RELOAD=1)"
elif command -v pa_reload_webapp.py >/dev/null 2>&1; then
  echo "==> Rechargement de $PA_DOMAIN"
  pa_reload_webapp.py "$PA_DOMAIN"
else
  echo "==> pa_reload_webapp.py indisponible : rechargez l'application depuis l'onglet Web."
fi

echo "==> Déploiement terminé avec succès."
