import os
from pathlib import Path

# Charge le fichier .env
env_file = Path('/home/myschoolgn/.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                os.environ[key] = value

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

application = get_wsgi_application()
