"""
Vue d'activation de licence en ligne.
Affiche un formulaire où l'utilisateur entre sa clé XXXX-XXXX-XXXX-XXXX-XXXX
et qui appelle license_manager.activate_online().

Cette vue est exemptée par le middleware (sinon l'utilisateur bloqué ne
pourrait jamais activer sa licence !).
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods


_PAGE_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MySchoolGN — Activation de licence</title>
<style>
  body {{ font-family: Arial, sans-serif; background: #1a3a5c;
          display: flex; align-items: center; justify-content: center;
          min-height: 100vh; margin: 0; padding: 20px; }}
  .card {{ background: white; border-radius: 12px; padding: 40px;
            max-width: 560px; width: 100%; box-shadow: 0 8px 32px rgba(0,0,0,0.3); }}
  h1 {{ color: #1a3a5c; font-size: 1.5rem; margin: 0 0 8px; text-align: center; }}
  .subtitle {{ color: #666; text-align: center; margin-bottom: 30px; font-size: 0.95rem; }}
  label {{ display: block; color: #444; font-weight: bold; margin: 12px 0 6px; font-size: 0.9rem; }}
  input[type=text] {{ width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px;
                       font-size: 1.1rem; font-family: monospace; box-sizing: border-box;
                       text-transform: uppercase; letter-spacing: 1px; }}
  input[type=text]:focus {{ outline: none; border-color: #1a3a5c; }}
  button {{ width: 100%; padding: 14px; background: #1a3a5c; color: white; border: none;
             border-radius: 6px; font-size: 1rem; font-weight: bold; cursor: pointer;
             margin-top: 20px; }}
  button:hover {{ background: #0d2438; }}
  .machine-id {{ background: #f5f7fa; padding: 12px; border-radius: 6px;
                  font-family: monospace; font-size: 0.85rem; color: #555;
                  word-break: break-all; margin-top: 8px; }}
  .alert {{ padding: 14px 16px; border-radius: 6px; margin-bottom: 20px; font-size: 0.95rem; }}
  .alert-success {{ background: #d4edda; border: 1px solid #c3e6cb; color: #155724; }}
  .alert-error {{ background: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; }}
  .info-row {{ display: flex; justify-content: space-between; padding: 4px 0;
                font-size: 0.9rem; color: #555; }}
  .footer {{ text-align: center; margin-top: 24px; color: #999; font-size: 0.85rem; }}
  a {{ color: #1a3a5c; }}
</style>
</head>
<body>
<div class="card">
  <h1>🔑 Activation de licence</h1>
  <p class="subtitle">MySchoolGN — Saisissez la clé fournie par l'administrateur FARA LENO AU +224622613559</p>

  {alert}

  <form method="POST" autocomplete="off">
    <label for="license_key">Clé de licence</label>
    <input type="text" id="license_key" name="license_key"
           placeholder="XXXX-XXXX-XXXX-XXXX-XXXX"
           value="{prefilled_key}"
           maxlength="29" required autofocus>

    <label>ID de cette machine</label>
    <div class="machine-id">{machine_id}</div>

    <button type="submit">Activer la licence</button>
  </form>

  <div class="footer">
    Besoin d'aide ? Contactez l'administrateur <strong>FARA LENO AU +224622613559</strong><br>
    <a href="/">← Retour à l'accueil</a>
  </div>
</div>
</body>
</html>"""


def _render(alert_html: str = '', prefilled_key: str = '', status_code: int = 200):
    try:
        import license_manager
        mid = license_manager.get_machine_id()
    except Exception:
        mid = 'Indisponible'

    html = _PAGE_HTML.format(
        alert=alert_html,
        prefilled_key=prefilled_key.replace('"', '&quot;'),
        machine_id=mid,
    )
    return HttpResponse(html, status=status_code, content_type='text/html; charset=utf-8')


@csrf_exempt  # accessible même quand l'utilisateur est bloqué (pas de session login)
@require_http_methods(['GET', 'POST'])
def activer_licence(request):
    if request.method == 'GET':
        return _render()

    key = (request.POST.get('license_key') or '').strip().upper()
    if not key:
        return _render(
            alert_html='<div class="alert alert-error">⚠ Veuillez saisir une clé.</div>',
            status_code=400,
        )

    try:
        import license_manager
        result = license_manager.activate_online(key)
    except Exception as e:
        return _render(
            alert_html=f'<div class="alert alert-error">⚠ Erreur technique : {e}</div>',
            prefilled_key=key,
            status_code=500,
        )

    if result.get('valid'):
        # Invalider le cache du middleware pour que le statut soit pris en compte immédiatement
        try:
            from ecole_moderne.licence_middleware import _license_cache
            _license_cache['checked_at'] = 0
            _license_cache['valid'] = None
        except Exception:
            pass

        success_html = (
            '<div class="alert alert-success">'
            '<strong>✓ Licence activée avec succès !</strong><br><br>'
            f'<div class="info-row"><span>École</span><strong>{result.get("school","")}</strong></div>'
            f'<div class="info-row"><span>Édition</span><strong>{result.get("edition","Standard")}</strong></div>'
            f'<div class="info-row"><span>Expire le</span><strong>{result.get("expires_at","")}</strong></div>'
            f'<div class="info-row"><span>Reste</span><strong>{result.get("days_left",0)} jour(s)</strong></div>'
            '<br><a href="/" style="display:block;text-align:center;padding:10px;'
            'background:#28a745;color:white;text-decoration:none;border-radius:6px;'
            'font-weight:bold;margin-top:8px;">→ Accéder à l\'application</a>'
            '</div>'
        )
        return _render(alert_html=success_html, prefilled_key=key)

    return _render(
        alert_html=f'<div class="alert alert-error">⚠ {result.get("reason","Activation refusée.")}</div>',
        prefilled_key=key,
        status_code=403,
    )
