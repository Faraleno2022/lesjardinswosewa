import json
import secrets
from uuid import UUID

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from eleves.models import Ecole
from utilisateurs.utils import user_is_admin, user_school

from .engine import apply_sync_change, snapshot_changes_for_ecole
from .models import SyncChange, SyncDevice


# Fraicheur de `derniere_connexion` : voir _device_from_headers.
CONNEXION_REFRESH_SECONDS = 60


def _json_body(request):
    if not request.body:
        return {}
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _current_school(user, data=None):
    if user and user.is_authenticated and user.is_superuser and data and data.get('ecole_id'):
        return Ecole.objects.filter(pk=data['ecole_id']).first()
    if user and user.is_authenticated:
        return user_school(user)
    if data and data.get('ecole_id'):
        return Ecole.objects.filter(pk=data['ecole_id']).first()
    return None


def _has_sync_admin_access(request):
    token = request.headers.get('X-Sync-Admin-Token', '')
    expected = getattr(settings, 'MYSCHOOL_SYNC_ADMIN_TOKEN', '')
    if expected and token and secrets.compare_digest(token, expected):
        return True
    user = getattr(request, 'user', None)
    return bool(user and user.is_authenticated and user_is_admin(user))


def _device_from_headers(request):
    device_id = request.headers.get('X-Sync-Device')
    token = request.headers.get('X-Sync-Token')
    if not device_id or not token:
        return None, JsonResponse({'ok': False, 'error': 'Identifiants de synchronisation manquants.'}, status=401)
    try:
        UUID(device_id)
    except ValueError:
        return None, JsonResponse({'ok': False, 'error': 'Identifiant appareil invalide.'}, status=400)

    device = SyncDevice.objects.select_related('ecole').filter(device_id=device_id, actif=True).first()
    if not device or not device.verifier_token(token):
        return None, JsonResponse({'ok': False, 'error': 'Appareil non autorise.'}, status=403)
    # Les postes interrogent le serveur toutes les quelques secondes pour que
    # les ajouts apparaissent tout de suite. Reecrire l'horodatage a chaque
    # appel ajouterait autant d'ecritures inutiles : une par minute suffit a
    # savoir qu'un poste est en ligne.
    derniere = device.derniere_connexion
    if not derniere or (timezone.now() - derniere).total_seconds() > CONNEXION_REFRESH_SECONDS:
        device.marquer_connexion()
    return device, None


def _schools_for_user(user):
    if user.is_superuser:
        return Ecole.objects.all().order_by('nom')
    ecole = user_school(user)
    if ecole:
        return Ecole.objects.filter(pk=ecole.pk)
    return Ecole.objects.none()


@require_GET
def health(request):
    return JsonResponse({
        'ok': True,
        'service': 'myschoolgn-sync',
        'version': 1,
        'server_time': timezone.now().isoformat(),
    })


@login_required
def device_setup(request):
    if not user_is_admin(request.user):
        return render(request, 'utilisateurs/permission_denied.html', status=403)

    ecoles = _schools_for_user(request.user)
    generated = None

    if request.method == 'POST':
        ecole_id = request.POST.get('ecole_id')
        nom = (request.POST.get('nom') or 'Poste local').strip()[:120]
        ecole = ecoles.filter(pk=ecole_id).first()

        if not ecole:
            messages.error(request, "Ecole introuvable ou non autorisee.")
        else:
            token = secrets.token_urlsafe(32)
            device = SyncDevice(ecole=ecole, nom=nom or 'Poste local')
            device.definir_token(token)
            device.save()

            server_url = request.build_absolute_uri('/').rstrip('/')
            generated = {
                'device': device,
                'token': token,
                'server_url': server_url,
                'env_block': "\n".join([
                    f"MYSCHOOL_SYNC_SERVER_URL={server_url}",
                    f"MYSCHOOL_SYNC_DEVICE_ID={device.device_id}",
                    f"MYSCHOOL_SYNC_TOKEN={token}",
                    f"MYSCHOOL_SYNC_ECOLE_ID={ecole.id}",
                ]),
            }
            messages.success(request, "Identifiants de synchronisation generes. Copiez-les maintenant.")

    return render(request, 'synchronisation/device_setup.html', {
        'titre_page': 'Connexion offline',
        'ecoles': ecoles,
        'generated': generated,
    })


@csrf_exempt
@require_POST
def register_device(request):
    if not _has_sync_admin_access(request):
        return JsonResponse({'ok': False, 'error': 'Permission refusee.'}, status=403)

    data = _json_body(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'JSON invalide.'}, status=400)

    ecole = _current_school(request.user, data)
    if not ecole:
        return JsonResponse({'ok': False, 'error': 'Aucune ecole associee a cet utilisateur.'}, status=400)

    nom = (data.get('nom') or data.get('name') or 'Poste local').strip()[:120]
    token = secrets.token_urlsafe(32)
    device = SyncDevice(ecole=ecole, nom=nom)
    device.definir_token(token)
    device.save()

    return JsonResponse({
        'ok': True,
        'device_id': str(device.device_id),
        'sync_token': token,
        'ecole_id': ecole.id,
        'message': 'Conservez ce token sur le poste local. Il ne sera plus affiche.',
    }, status=201)


def _client_change_id(change):
    """Identifiant du changement sur le poste emetteur, si celui-ci le fournit."""
    raw = change.get('client_change_id')
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _previous_submission(device, change, model_label, object_uuid):
    """
    Retrouve l'envoi precedent du meme changement par le meme poste.

    Sans cela, un changement refuse est repousse a chaque cycle et empile une
    nouvelle ligne en echec cote serveur. Les postes anterieurs a cette version
    n'envoient pas d'identifiant : on retombe alors sur l'ancien comportement.
    """
    client_change_id = _client_change_id(change)
    if not client_change_id:
        return None
    previous = SyncChange.objects.filter(
        device=device, client_change_id=client_change_id,
    ).first()
    if not previous:
        return None
    # Garde-fou : une base locale reinitialisee reutilise les memes numeros.
    if previous.model_label != model_label or previous.object_uuid != object_uuid:
        return None
    return previous


@csrf_exempt
@require_POST
def push(request):
    device, error_response = _device_from_headers(request)
    if error_response:
        return error_response

    data = _json_body(request)
    if data is None:
        return JsonResponse({'ok': False, 'error': 'JSON invalide.'}, status=400)

    changes = data.get('changes', [])
    if not isinstance(changes, list):
        return JsonResponse({'ok': False, 'error': 'Le champ changes doit etre une liste.'}, status=400)

    accepted = []
    rejected = []
    already_applied = 0
    valid_operations = {choice[0] for choice in SyncChange.OPERATION_CHOICES}

    for index, change in enumerate(changes):
        if not isinstance(change, dict):
            rejected.append({'index': index, 'error': 'Changement invalide.'})
            continue

        operation = (change.get('operation') or '').upper()
        model_label = (change.get('model') or change.get('model_label') or '').strip()
        payload = change.get('payload') or {}
        raw_uuid = change.get('object_uuid')

        if operation not in valid_operations:
            rejected.append({'index': index, 'error': 'Operation invalide.'})
            continue
        if not model_label:
            rejected.append({'index': index, 'error': 'Modele manquant.'})
            continue
        if not isinstance(payload, dict):
            rejected.append({'index': index, 'error': 'Payload invalide.'})
            continue

        object_uuid = None
        if raw_uuid:
            try:
                object_uuid = UUID(str(raw_uuid))
            except ValueError:
                rejected.append({'index': index, 'error': 'UUID objet invalide.'})
                continue

        if object_uuid and 'sync_uuid' not in payload:
            payload = {**payload, 'sync_uuid': str(object_uuid)}

        model_label = model_label[:120]
        previous = _previous_submission(device, change, model_label, object_uuid)

        if previous and previous.statut == SyncChange.STATUT_APPLIED:
            # Renvoi d'un changement deja applique (accuse de reception perdu).
            # On le reconnait sans le rejouer ni empiler une ligne de plus.
            already_applied += 1
            accepted.append({'index': index, 'change_id': previous.id})
            continue

        tentatives = 0
        if previous:
            # Un renvoi remplace l'essai precedent au lieu de s'empiler. La
            # ligne est recreee en fin de file : `pull` sert les changements
            # par id croissant, une ligne reutilisee resterait invisible des
            # postes ayant deja depasse son numero.
            tentatives = previous.tentatives or 0
            previous.delete()

        sync_change = SyncChange.objects.create(
            ecole=device.ecole,
            device=device,
            model_label=model_label,
            object_uuid=object_uuid,
            operation=operation,
            payload=payload,
            tentatives=tentatives,
            client_change_id=_client_change_id(change),
        )

        try:
            apply_sync_change(sync_change)
            accepted.append({'index': index, 'change_id': sync_change.id})
        except Exception as exc:
            sync_change.statut = SyncChange.STATUT_FAILED
            sync_change.erreur = str(exc)
            sync_change.tentatives = (sync_change.tentatives or 0) + 1
            sync_change.save(update_fields=['statut', 'erreur', 'tentatives'])
            rejected.append({'index': index, 'change_id': sync_change.id, 'error': str(exc)})

    return JsonResponse({
        'ok': True,
        'accepted_count': len(accepted),
        'rejected_count': len(rejected),
        'already_applied_count': already_applied,
        'accepted': accepted,
        'rejected': rejected,
        'server_time': timezone.now().isoformat(),
    })


def _watermark_for_device(device, since_id):
    """
    Repere jusqu'ou le poste peut avancer quand le lot est vide.

    Sans cela, `since_id` restait fige des qu'un changement ne le concernait
    pas (le sien, ou un envoi refuse d'un autre poste) : le poste redemandait
    alors ce meme intervalle a chaque cycle. En avancant le repere, ses
    verifications suivantes ne coutent plus rien tant que rien ne bouge, ce
    qui rend une cadence de quelques secondes tenable.

    Les lignes poussees par un poste et encore en attente sont exclues : elles
    sont en cours d'application au moment meme de la lecture et deviendront
    livrables dans l'instant. Les depasser les rendrait invisibles a jamais.
    """
    dernier = (
        SyncChange.objects
        .filter(ecole=device.ecole)
        .exclude(device__isnull=False, statut=SyncChange.STATUT_PENDING)
        .aggregate(dernier=Max('id'))['dernier']
    )
    if not dernier:
        return since_id
    try:
        return max(int(since_id), dernier) if since_id else dernier
    except (TypeError, ValueError):
        return dernier


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def pull(request):
    device, error_response = _device_from_headers(request)
    if error_response:
        return error_response

    since = request.GET.get('since')
    since_id = request.GET.get('since_id')
    initial = request.GET.get('initial') in {'1', 'true', 'yes'}
    if request.method == 'POST':
        data = _json_body(request)
        if data is None:
            return JsonResponse({'ok': False, 'error': 'JSON invalide.'}, status=400)
        since = data.get('since') or since
        since_id = data.get('since_id') or since_id
        initial = data.get('initial') in {True, '1', 'true', 'yes'}

    if initial:
        # Repere releve avant l'instantane : le poste neuf reprend ensuite le
        # fil a cet endroit, au lieu de rejouer tout l'historique des
        # changements qui l'ont precede — historique deja contenu dans
        # l'instantane, mais que rien ne lui disait de sauter. Pris avant, il
        # ne peut que faire redescendre deux fois un changement concurrent, ce
        # qui est sans effet : l'application se fait par `sync_uuid`.
        repere = _watermark_for_device(device, since_id)
        serialized_changes = snapshot_changes_for_ecole(device.ecole)
        return JsonResponse({
            'ok': True,
            'device_id': str(device.device_id),
            'ecole_id': device.ecole_id,
            'since': since,
            'since_id': since_id,
            'initial': True,
            'changes': serialized_changes,
            'latest_change_id': repere,
            'server_time': timezone.now().isoformat(),
        })

    # Deux origines doivent etre servies aux postes :
    #  - les changements pousses par un autre poste puis appliques ici ;
    #  - ceux nes sur ce serveur meme (saisie dans le site en ligne). Ceux-la
    #    sont crees par le signal local et restent PENDING, faute d'un poste a
    #    qui les pousser ; ils sont pourtant deja dans la base, donc bons a
    #    distribuer. Les ignorer rendait toute saisie en ligne invisible des
    #    postes.
    changes = SyncChange.objects.filter(ecole=device.ecole).filter(
        Q(statut=SyncChange.STATUT_APPLIED)
        | Q(device__isnull=True, statut=SyncChange.STATUT_PENDING)
    ).exclude(device=device)
    if since_id:
        try:
            changes = changes.filter(id__gt=int(since_id))
        except (TypeError, ValueError):
            return JsonResponse({'ok': False, 'error': 'since_id invalide.'}, status=400)
    elif since:
        parsed_since = parse_datetime(str(since))
        if not parsed_since:
            return JsonResponse({'ok': False, 'error': 'since invalide. Utilisez une date ISO ou since_id.'}, status=400)
        if timezone.is_naive(parsed_since):
            parsed_since = timezone.make_aware(parsed_since, timezone.get_current_timezone())
        changes = changes.filter(date_creation__gt=parsed_since)

    # Le repere est releve AVANT de lire le lot, jamais apres. Un changement
    # enregistre entre les deux requetes serait sinon compte par le repere sans
    # figurer dans le lot : le poste avancerait son `since_id` par-dessus une
    # donnee qu'il n'a jamais recue, et celle-ci ne lui serait plus jamais
    # servie. Pris avant, le repere reste au pire en retard d'un cycle.
    repere = _watermark_for_device(device, since_id)

    changes = changes.order_by('id')[:200]
    serialized_changes = [
        {
            'id': change.id,
            'model': change.model_label,
            'model_label': change.model_label,
            'object_uuid': str(change.object_uuid) if change.object_uuid else None,
            'operation': change.operation,
            'payload': change.payload,
            'device_id': str(change.device.device_id) if change.device else None,
            'device_name': change.device.nom if change.device else None,
            'date_creation': change.date_creation.isoformat(),
        }
        for change in changes
    ]

    return JsonResponse({
        'ok': True,
        'device_id': str(device.device_id),
        'ecole_id': device.ecole_id,
        'since': since,
        'since_id': since_id,
        'changes': serialized_changes,
        'latest_change_id': (
            serialized_changes[-1]['id'] if serialized_changes else repere
        ),
        'server_time': timezone.now().isoformat(),
    })


@require_GET
def state(request):
    """
    Filigrane de fraicheur des donnees de l'ecole : identifiant du dernier
    changement enregistre localement.

    Deux appelants s'en servent, et c'est ce qui rend la propagation visible
    tout de suite :
      - le worker du poste, qui evite un `pull` complet tant que le filigrane
        n'a pas bouge : la cadence peut donc etre serree sans charger le
        serveur ;
      - les pages ouvertes dans le navigateur, qui se rafraichissent des
        qu'une donnee arrive d'un autre poste.

    L'appelant s'authentifie soit par les en-tetes appareil, soit par sa
    session : la meme vue sert le serveur en ligne et les postes locaux.
    """
    ecole = None
    if request.headers.get('X-Sync-Device'):
        device, error_response = _device_from_headers(request)
        if error_response:
            return error_response
        ecole = device.ecole
    else:
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return JsonResponse({'ok': False, 'error': 'Authentification requise.'}, status=401)
        ecole = _current_school(user)

    changes = SyncChange.objects.all()
    if ecole:
        changes = changes.filter(ecole=ecole)
    last_change_id = changes.aggregate(dernier=Max('id'))['dernier'] or 0

    response = JsonResponse({
        'ok': True,
        'ecole_id': ecole.pk if ecole else None,
        'last_change_id': last_change_id,
        'server_time': timezone.now().isoformat(),
    })
    # Sans cela, un cache intermediaire figerait le filigrane et les postes
    # continueraient d'afficher des donnees perimees.
    response['Cache-Control'] = 'no-store, max-age=0'
    return response
