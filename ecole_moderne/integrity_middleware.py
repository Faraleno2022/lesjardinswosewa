"""Controle d'integrite de l'application desktop MySchoolGN."""

import time

from django.http import HttpResponse


_integrity_cache = {'valid': None, 'checked_at': 0, 'reason': ''}
_INTEGRITY_TTL = 600


def _check_integrity_cached() -> dict:
    global _integrity_cache
    now = time.time()
    if (
        _integrity_cache['valid'] is None
        or now - _integrity_cache['checked_at'] > _INTEGRITY_TTL
    ):
        try:
            import integrity_check

            result = integrity_check.verify()
            _integrity_cache = {
                'valid': result.get('valid', True),
                'reason': result.get('reason', ''),
                'checked_at': now,
            }
        except ImportError:
            _integrity_cache = {
                'valid': True,
                'reason': 'dev_mode',
                'checked_at': now,
            }
        except Exception:
            _integrity_cache = {
                'valid': True,
                'reason': '',
                'checked_at': now,
            }
    return _integrity_cache


_TAMPERED_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MySchoolGN — Application corrompue</title>
<style>
  body { font-family: Arial, sans-serif; background: #2c0b0e;
         display: flex; align-items: center; justify-content: center;
         min-height: 100vh; margin: 0; }
  .card { background: white; border-radius: 12px; padding: 48px 40px;
          max-width: 480px; width: 90%; text-align: center;
          box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
  h1 { color: #c0392b; font-size: 1.6rem; margin-bottom: 8px; }
  .icon { font-size: 4rem; margin-bottom: 16px; }
  p { color: #555; line-height: 1.6; }
  .reason { background: #fdf2f2; border: 1px solid #f5c6cb;
            border-radius: 6px; padding: 12px 16px; color: #c0392b;
            font-weight: bold; margin: 20px 0; }
</style>
</head>
<body>
<div class="card">
  <div class="icon">&#x1F6A8;</div>
  <h1>Application corrompue</h1>
  <p>Des fichiers de <strong>MySchoolGN</strong> ont été modifiés.<br>
     L'application ne peut pas fonctionner en toute sécurité.</p>
  <div class="reason">Modification non autorisée détectée</div>
  <p>Veuillez réinstaller l'application depuis le programme officiel.</p>
</div>
</body>
</html>"""


class IntegrityMiddleware:
    """Laisse toujours passer une application intacte, sans aucune licence."""

    EXEMPT_PREFIXES = (
        '/static/', '/media/', '/favicon', '/utilisateurs/login/',
        '/admin/', '/api/v1/sync/', '/api/v1/updates/', '/rapport-scolaire/',
    )
    EXEMPT_EXACT = {
        '/', '/index/', '/robots.txt', '/sitemap.xml', '/fonctionnalites/',
        '/tarifs/', '/contact/', '/demo/', '/utilisateurs/login/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        from django.conf import settings

        admin_path = '/' + getattr(settings, 'ADMIN_URL', 'admin/')
        if path.startswith(admin_path):
            return self.get_response(request)
        if any(path.startswith(prefix) for prefix in self.EXEMPT_PREFIXES):
            return self.get_response(request)
        if path in self.EXEMPT_EXACT:
            return self.get_response(request)

        integrity = _check_integrity_cached()
        if not integrity['valid']:
            return HttpResponse(
                _TAMPERED_HTML,
                status=403,
                content_type='text/html; charset=utf-8',
            )
        return self.get_response(request)
