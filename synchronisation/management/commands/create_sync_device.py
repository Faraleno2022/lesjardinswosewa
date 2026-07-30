import secrets

from django.core.management.base import BaseCommand, CommandError

from eleves.models import Ecole
from synchronisation.models import SyncDevice


class Command(BaseCommand):
    help = "Create a synchronization device and print its one-time token."

    def add_arguments(self, parser):
        parser.add_argument('--ecole-id', type=int, required=True)
        parser.add_argument('--nom', default='Poste local')

    def handle(self, *args, **options):
        ecole = Ecole.objects.filter(pk=options['ecole_id']).first()
        if not ecole:
            raise CommandError(f"Ecole introuvable: {options['ecole_id']}")

        token = secrets.token_urlsafe(32)
        device = SyncDevice(ecole=ecole, nom=options['nom'][:120])
        device.definir_token(token)
        device.save()

        self.stdout.write(self.style.SUCCESS('Appareil de synchronisation cree.'))
        self.stdout.write(f"MYSCHOOL_SYNC_DEVICE_ID={device.device_id}")
        self.stdout.write(f"MYSCHOOL_SYNC_TOKEN={token}")
        self.stdout.write(f"MYSCHOOL_SYNC_ECOLE_ID={ecole.id}")
