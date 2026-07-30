"""
Vues spécifiques au mode Desktop (application autonome hors-ligne).

Permet d'arrêter complètement le serveur local depuis l'interface, afin de
libérer le port/les ressources et pouvoir lancer une autre application.
Ces vues ne sont actives QUE lorsque l'application tourne en mode hors-ligne
(variable d'environnement OFFLINE_MODE=1, positionnée par run_server.py).
"""
import os
import sys
import threading
import time

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_POST


def _is_offline():
    """Vrai uniquement quand l'app est lancée depuis l'exe desktop."""
    return os.environ.get('OFFLINE_MODE', '0') == '1'


def csrf_failure(request, reason=''):
    """Page conviviale en cas d'échec de vérification CSRF.

    Se produit typiquement quand un formulaire est soumis après expiration de
    la session/du jeton. Remplace la page 403 brute de Django par un message
    professionnel avec un bouton pour revenir en arrière.
    """
    referer = request.META.get('HTTP_REFERER') or '/'
    return render(request, 'csrf_failure.html', {
        'reason': reason,
        'back_url': referer,
    }, status=403)


@login_required
@require_POST
def arreter_application(request):
    """Arrête complètement l'application desktop (serveur local inclus).

    - Réservé au mode desktop (OFFLINE_MODE) : renvoie 403 sur le serveur web.
    - Affiche une page d'au revoir qui ferme la fenêtre, puis termine le
      processus après un court délai (le temps que la réponse s'affiche).
      os._exit() tue tout le processus -> le port est libéré immédiatement.
    """
    if not _is_offline():
        return HttpResponseForbidden(
            "Cette action n'est disponible que dans l'application desktop."
        )

    def _shutdown():
        # Laisser la réponse HTTP partir et la page s'afficher avant de couper.
        time.sleep(1.5)
        try:
            sys.stdout.flush()
            sys.stderr.flush()
        except Exception:
            pass
        # Termine TOUT le processus (serveur Django + threads) -> libère le port.
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()
    return render(request, 'desktop/application_fermee.html')
