import json
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Register this offline installation against the online sync server."

    def add_arguments(self, parser):
        parser.add_argument('--server-url', default=getattr(settings, 'MYSCHOOL_SYNC_SERVER_URL', ''))
        parser.add_argument('--admin-token', default=getattr(settings, 'MYSCHOOL_SYNC_ADMIN_TOKEN', ''))
        parser.add_argument('--ecole-id', default=getattr(settings, 'MYSCHOOL_SYNC_ECOLE_ID', ''))
        parser.add_argument('--nom', default='Poste local')

    def handle(self, *args, **options):
        server_url = (options['server_url'] or '').rstrip('/')
        admin_token = options['admin_token'] or ''
        ecole_id = options['ecole_id'] or ''
        nom = options['nom'] or 'Poste local'

        if not server_url:
            raise CommandError('MYSCHOOL_SYNC_SERVER_URL manquant.')
        if not admin_token:
            raise CommandError('MYSCHOOL_SYNC_ADMIN_TOKEN manquant.')
        if not ecole_id:
            raise CommandError('MYSCHOOL_SYNC_ECOLE_ID manquant.')

        payload = json.dumps({'nom': nom, 'ecole_id': ecole_id}).encode('utf-8')
        req = urlrequest.Request(
            f'{server_url}/api/v1/sync/devices/register/',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Sync-Admin-Token': admin_token,
            },
            method='POST',
        )

        try:
            with urlrequest.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise CommandError(f"Erreur serveur {exc.code}: {detail}") from exc
        except URLError as exc:
            raise CommandError(f"Serveur de synchronisation inaccessible: {exc}") from exc

        if not data.get('ok'):
            raise CommandError(data.get('error') or 'Enregistrement refuse.')

        self.stdout.write(self.style.SUCCESS('Poste offline enregistre.'))
        self.stdout.write('Ajoutez ces valeurs dans le .env du poste offline:')
        self.stdout.write(f"MYSCHOOL_SYNC_DEVICE_ID={data['device_id']}")
        self.stdout.write(f"MYSCHOOL_SYNC_TOKEN={data['sync_token']}")
        self.stdout.write(f"MYSCHOOL_SYNC_ECOLE_ID={data['ecole_id']}")
