"""
Production settings for ecole_moderne.
Use environment variables to configure secrets and database (MySQL on PythonAnywhere).
"""

from .paramètres import *  # noqa
import os

# ===== Mode production =====
DEBUG = False

# ===== Hôtes autorisés =====
ALLOWED_HOSTS = [
    'gshadjakanfingdiane.pythonanywhere.com',
    'myschoolgn.space',
    'www.myschoolgn.space',
    'myschool-rn3d.onrender.com',
]

# ===== Origines CSRF de confiance =====
CSRF_TRUSTED_ORIGINS = [
    'https://gshadjakanfingdiane.pythonanywhere.com',
    'https://myschoolgn.space',
    'https://www.myschoolgn.space',
    'https://myschool-rn3d.onrender.com',
]

# ===== Proxy headers (PythonAnywhere) =====
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

# ===== HTTPS et cookies sécurisés =====
FORCE_SSL = True
SECURE_SSL_REDIRECT = FORCE_SSL
SESSION_COOKIE_SECURE = FORCE_SSL
CSRF_COOKIE_SECURE = FORCE_SSL

# ===== HSTS =====
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# ===== Base de données MySQL =====
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DJANGO_DB_NAME', ''),
        'USER': os.environ.get('DJANGO_DB_USER', ''),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
        'HOST': os.environ.get('DJANGO_DB_HOST', ''),
        'PORT': os.environ.get('DJANGO_DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
        },
        'CONN_MAX_AGE': 60,
    }
}

# ===== Fichiers statiques et médias =====
BASE_DIR_SERVER = os.getenv('PROJECT_BASE_DIR', '/home/myschoolgn/myschool-')

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR_SERVER, 'staticfiles')

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR_SERVER, 'media')

# ===== Logging =====
LOG_DIR = os.path.join(BASE_DIR_SERVER, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

# ===== Email (optionnel) =====
EMAIL_BACKEND = os.getenv('DJANGO_EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('DJANGO_EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('DJANGO_EMAIL_PORT', '25'))
EMAIL_HOST_USER = os.getenv('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('DJANGO_EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.getenv('DJANGO_EMAIL_USE_TLS', 'false').lower() in ('1', 'true', 'yes')
EMAIL_USE_SSL = os.getenv('DJANGO_EMAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
DEFAULT_FROM_EMAIL = os.getenv('DJANGO_DEFAULT_FROM_EMAIL', 'contact@myschoolgn.space')

# ===== URL du site pour les emails =====
SITE_BASE_URL = 'https://www.myschoolgn.space'

# ===== Import éventuel des overrides locaux =====
try:
    from .local_settings import *  # noqa
except ImportError:
    pass
