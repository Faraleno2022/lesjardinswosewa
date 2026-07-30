import json
from urllib import parse, request as urlrequest
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from eleves.models import Ecole
from synchronisation.engine import apply_sync_change
from synchronisation.models import SyncChange


class Command(BaseCommand):
    help = "Push local pending sync changes and pull changes from other offline devices."

    def add_arguments(self, parser):
        parser.add_argument('--server-url', default=getattr(settings, 'MYSCHOOL_SYNC_SERVER_URL', ''))
        parser.add_argument('--device-id', default=getattr(settings, 'MYSCHOOL_SYNC_DEVICE_ID', ''))
        parser.add_argument('--token', default=getattr(settings, 'MYSCHOOL_SYNC_TOKEN', ''))
        parser.add_argument('--ecole-id', default=getattr(settings, 'MYSCHOOL_SYNC_ECOLE_ID', ''))
        parser.add_argument('--since-id', default='')
        parser.add_argument('--initial', action='store_true')
        parser.add_argument('--pull-only', action='store_true')
        parser.add_argument('--push-only', action='store_true')

    def handle(self, *args, **options):
        server_url = (options['server_url'] or '').rstrip('/')
        device_id = options['device_id'] or ''
        token = options['token'] or ''
        ecole_id = options['ecole_id'] or ''

        if not server_url or not device_id or not token or not ecole_id:
            raise CommandError(
                'Configuration incomplete. Definissez MYSCHOOL_SYNC_SERVER_URL, '
                'MYSCHOOL_SYNC_DEVICE_ID, MYSCHOOL_SYNC_TOKEN et MYSCHOOL_SYNC_ECOLE_ID.'
            )

        ecole = Ecole.objects.filter(pk=ecole_id).first()
        if not ecole:
            raise CommandError(f"Ecole locale introuvable: {ecole_id}")

        if not options['pull_only']:
            pushed = self._push_pending(server_url, device_id, token, ecole)
            self.stdout.write(self.style.SUCCESS(f'{pushed} changement(s) envoye(s).'))

        if not options['push_only']:
            pulled = self._pull_changes(server_url, device_id, token, ecole, options['since_id'], options['initial'])
            self.stdout.write(self.style.SUCCESS(f'{pulled} changement(s) recu(s).'))

    def _request_json(self, url, device_id, token, payload=None, method='POST'):
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        req = urlrequest.Request(
            url,
            data=body,
            headers={
                'Content-Type': 'application/json',
                'X-Sync-Device': device_id,
                'X-Sync-Token': token,
            },
            method=method,
        )
        try:
            with urlrequest.urlopen(req, timeout=45) as response:
                return json.loads(response.read().decode('utf-8'))
        except HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise CommandError(f"Erreur serveur {exc.code}: {detail}") from exc
        except URLError as exc:
            raise CommandError(f"Serveur de synchronisation inaccessible: {exc}") from exc

    def _push_pending(self, server_url, device_id, token, ecole):
        pending = list(
            SyncChange.objects
            .filter(ecole=ecole, statut=SyncChange.STATUT_PENDING)
            .order_by('id')[:200]
        )
        if not pending:
            return 0

        response = self._request_json(
            f'{server_url}/api/v1/sync/push/',
            device_id,
            token,
            {
                'changes': [
                    {
                        'model': change.model_label,
                        'object_uuid': str(change.object_uuid) if change.object_uuid else None,
                        'operation': change.operation,
                        'payload': change.payload,
                    }
                    for change in pending
                ]
            },
        )
        if not response.get('ok'):
            raise CommandError(response.get('error') or 'Push refuse.')

        accepted_indexes = {item['index'] for item in response.get('accepted', [])}
        now = timezone.now()
        updated = 0
        for index, change in enumerate(pending):
            if index in accepted_indexes:
                change.statut = SyncChange.STATUT_APPLIED
                change.date_application = now
                change.save(update_fields=['statut', 'date_application'])
                updated += 1
        return updated

    def _pull_changes(self, server_url, device_id, token, ecole, since_id, initial=False):
        query = {}
        if since_id:
            query['since_id'] = since_id
        if initial:
            query['initial'] = '1'
        suffix = f"?{parse.urlencode(query)}" if query else ''
        response = self._request_json(
            f'{server_url}/api/v1/sync/pull/{suffix}',
            device_id,
            token,
            payload=None,
            method='GET',
        )
        if not response.get('ok'):
            raise CommandError(response.get('error') or 'Pull refuse.')

        created = 0
        for item in response.get('changes', []):
            server_change_id = item.get('id')
            if server_change_id and SyncChange.objects.filter(
                ecole=ecole,
                payload__server_change_id=server_change_id,
            ).exists():
                continue

            payload = item.get('payload') or {}
            if server_change_id:
                payload = {**payload, 'server_change_id': server_change_id}

            change = SyncChange.objects.create(
                ecole=ecole,
                model_label=item['model_label'],
                object_uuid=item.get('object_uuid') or None,
                operation=item['operation'],
                payload=payload,
            )
            try:
                apply_sync_change(change)
                created += 1
            except Exception as exc:
                change.statut = SyncChange.STATUT_FAILED
                change.erreur = str(exc)
                change.save(update_fields=['statut', 'erreur'])
                self.stderr.write(f"Changement {server_change_id} non applique: {exc}")

        latest_id = response.get('latest_change_id')
        if latest_id:
            self.stdout.write(f'Dernier changement serveur: {latest_id}')
        return created
