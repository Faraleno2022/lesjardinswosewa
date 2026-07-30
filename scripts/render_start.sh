#!/usr/bin/env bash
set -e

python manage.py migrate --noinput
python manage.py ensure_default_school
python manage.py ensure_render_admin
python manage.py collectstatic --noinput
gunicorn ecole_moderne.wsgi:application
