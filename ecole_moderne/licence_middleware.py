"""Middleware de vérification d'intégrité — MySchoolGN.

La licence reste un renseignement administratif et ne doit jamais empêcher
l'utilisation de l'application. Seule une altération des fichiers protégés
peut encore produire une réponse bloquante.
"""
import time
from django.http import HttpResponse


_integrity_cache = {'valid': None, 'checked_at': 0, 'reason': ''}
_INTEGRITY_TTL = 600  # 10 minutes


def _check_integrity_cached() -> dict:
    global _integrity_cache
    now = time.time()
    if now - _integrity_cache['checked_at'] > _INTEGRITY_TTL or _integrity_cache['valid'] is None:
        try:
            import integrity_check
            result = integrity_check.verify()
            _integrity_cache = {
                'valid': result.get('valid', True),
                'reason': result.get('reason', ''),
                'checked_at': now,
            }
        except ImportError:
            _integrity_cache = {'valid': True, 'reason': 'dev_mode', 'checked_at': now}
        except Exception:
            _integrity_cache = {'valid': True, 'reason': '', 'checked_at': now}
    return _integrity_cache


# ─── Page de blocage intégrité ────────────────────────────────────────────────
_TAMPERED_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MySchoolGN — Application corrompue</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #2c0b0e;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; margin: 0; }}
  .card {{ background: white; border-radius: 12px; padding: 48px 40px;
            max-width: 480px; width: 90%; text-align: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
  h1 {{ color: #c0392b; font-size: 1.6rem; margin-bottom: 8px; }}
  .icon {{ font-size: 4rem; margin-bottom: 16px; }}
  p {{ color: #555; line-height: 1.6; }}
  .reason {{ background: #fdf2f2; border: 1px solid #f5c6cb; border-radius: 6px;
              padding: 12px 16px; color: #c0392b; font-weight: bold; margin: 20px 0; }}
  .contact {{ background: #eaf4fb; border-radius: 6px; padding: 12px 16px;
               color: #1a5276; margin-top: 16px; }}
  small {{ color: #aaa; display: block; margin-top: 20px; font-size: 0.8rem; }}
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#x1F6A8;</div>
  <h1>Application corrompue</h1>
  <p>Des fichiers de <strong>MySchoolGN</strong> ont été modifiés.<br>
     L'application ne peut pas fonctionner en toute sécurité.</p>
  <div class="reason">Modification non autorisée détectée</div>
  <div class="contact">
    Veuillez réinstaller l'application depuis le programme officiel<br>
    ou contactez l'administrateur <strong>FARA LENO AU +224622613559</strong>
  </div>
  <small>Code erreur : INTEGRITY_VIOLATION</small>
</div>
</body>
</html>"""


class LicenceMiddleware:
    """
    Nom conservé pour la compatibilité des réglages existants.

    La licence et l'essai ne sont plus contrôlés ici. Le middleware vérifie
    uniquement l'intégrité et laisse toujours passer une application intacte.
    """

    EXEMPT_PREFIXES = (
        '/static/', '/media/', '/favicon', '/utilisateurs/login/',
        '/activer/', '/admin/', '/api/v1/license/', '/api/v1/sync/', '/rapport-scolaire/',
    )
    EXEMPT_EXACT = {
        '/',
        '/index/',
        '/robots.txt',
        '/sitemap.xml',
        '/fonctionnalites/',
        '/tarifs/',
        '/contact/',
        '/demo/',
        '/utilisateurs/login/',
        '/activer/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Ressources statiques et login toujours accessibles
        from django.conf import settings as _settings
        _admin_path = '/' + getattr(_settings, 'ADMIN_URL', 'admin/')
        if path.startswith(_admin_path):
            return self.get_response(request)
        if any(path.startswith(p) for p in self.EXEMPT_PREFIXES):
            return self.get_response(request)
        if path in self.EXEMPT_EXACT:
            return self.get_response(request)

        # Vérification intégrité (avec cache 10 min)
        integrity = _check_integrity_cached()
        if not integrity['valid']:
            return HttpResponse(
                _TAMPERED_HTML, status=403,
                content_type='text/html; charset=utf-8'
            )

        return self.get_response(request)
