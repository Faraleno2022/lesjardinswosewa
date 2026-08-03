import os
import sys
from pathlib import Path

# Le chemin est dérivé du projet au lieu de dépendre d'un compte
# PythonAnywhere particulier. settings.py charge ensuite BASE_DIR/.env.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')

application = get_wsgi_application()
