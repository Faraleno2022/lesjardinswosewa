"""
Diffusion des mises a jour de l'application Windows aux postes installes.

Le poste demande ici s'il existe une version plus recente que la sienne. La
reponse ne contient qu'un descripteur : numero, adresse du fichier et son
empreinte. Le telechargement lui-meme ne passe pas par ce serveur, qui
n'aurait ni la place ni la bande passante pour distribuer un installateur de
plusieurs centaines de megaoctets a chaque poste.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from ecole_moderne.version import est_plus_recente
from synchronisation.views import appareil_authentifie

from .models import VersionApplication


@require_GET
def derniere_version(request):
    """
    Descripteur de la derniere version publiee, s'il y en a une de plus
    recente que celle annoncee par le poste.

    Le poste transmet sa version courante en parametre. Le serveur repond donc
    par une decision — « rien pour toi » ou « voici quoi installer » — plutot
    que par un etat brut que chaque poste interpreterait a sa facon.
    """
    appareil, erreur = appareil_authentifie(request)
    if erreur:
        return erreur

    version_du_poste = (request.GET.get('version') or '').strip()
    derniere = VersionApplication.derniere_publiee()

    if not derniere or not est_plus_recente(derniere.version, version_du_poste):
        return JsonResponse({
            'ok': True,
            'mise_a_jour_disponible': False,
            'version_installee': version_du_poste,
            'server_time': timezone.now().isoformat(),
        })

    return JsonResponse({
        'ok': True,
        'mise_a_jour_disponible': True,
        'version': derniere.version,
        'url': derniere.url_telechargement,
        'sha256': derniere.sha256,
        'taille_octets': derniere.taille_octets,
        'notes': derniere.notes,
        'obligatoire': derniere.obligatoire,
        'version_installee': version_du_poste,
        'server_time': timezone.now().isoformat(),
    })


@require_GET
@login_required
def mise_a_jour_prete(request):
    """
    Signale a l'ecran qu'une version est telechargee et attend un redemarrage.

    L'installation a lieu au demarrage suivant, ce qui suffit pour un poste
    qu'on eteint le soir. Un poste laisse allume des semaines resterait
    autrement sur une version ancienne sans que personne ne le sache : ce
    point permet de le dire a l'utilisateur, qui redemarre quand cela
    l'arrange.

    Le serveur en ligne repond simplement qu'il n'y a rien : la mise a jour
    concerne l'application Windows, pas le site.
    """
    from ecole_moderne import auto_mise_a_jour

    try:
        descripteur = auto_mise_a_jour.mise_a_jour_en_attente()
    except Exception:
        descripteur = None

    if not descripteur:
        return JsonResponse({'ok': True, 'prete': False})

    return JsonResponse({
        'ok': True,
        'prete': True,
        'version': descripteur.get('version'),
        'notes': descripteur.get('notes') or '',
        'obligatoire': bool(descripteur.get('obligatoire')),
    })
