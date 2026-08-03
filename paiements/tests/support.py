"""Configuration partagée pour les tests HTTP du module paiements."""

from django.conf import settings


LICENCE_MIDDLEWARE = "ecole_moderne.licence_middleware.LicenceMiddleware"

# Les tests HTTP ne doivent pas dépendre d'une licence installée sur la machine
# qui les exécute. Toutes les autres couches de sécurité restent actives.
TEST_MIDDLEWARE = tuple(
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware != LICENCE_MIDDLEWARE
)
