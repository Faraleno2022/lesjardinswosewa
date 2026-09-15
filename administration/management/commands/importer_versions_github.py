"""
Recopie les publications GitHub dans la table des versions de l'application.

Le serveur le fait deja de lui-meme quand un poste vient demander s'il existe
une mise a jour. Cette commande sert aux deux cas ou cela ne suffit pas :
verifier tout de suite qu'une release fraichement publiee est bien vue (sans
attendre le quart d'heure du verrou), et alimenter un serveur qu'aucun poste
n'interroge encore.
"""
from django.core.management.base import BaseCommand

from administration import github_releases
from administration.models import VersionApplication
from ecole_moderne.version import APP_VERSION


class Command(BaseCommand):
    help = "Importe les versions publiees sur GitHub dans VersionApplication."

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite', type=int, default=10,
            help='Nombre de publications GitHub examinees (10 par defaut).',
        )

    def handle(self, *args, **options):
        depot = github_releases._depot()
        self.stdout.write(f'Depot          : {depot}')
        self.stdout.write(f'Version du code : {APP_VERSION}')

        creees, modifiees = github_releases.importer_versions(options['limite'])

        if creees:
            self.stdout.write(self.style.SUCCESS(
                f'{creees} version(s) importee(s) et mise(s) a disposition.'
            ))
        if modifiees:
            self.stdout.write(f'{modifiees} version(s) deja connue(s) rafraichie(s).')
        if not creees and not modifiees:
            self.stdout.write('Rien de nouveau.')

        derniere = VersionApplication.derniere_publiee()
        if derniere:
            self.stdout.write(
                f'Derniere version proposee aux postes : {derniere.version}'
            )
        else:
            self.stdout.write(self.style.WARNING(
                'Aucune version publiee : les postes ne verront aucune mise a jour. '
                'Verifiez que la release GitHub porte bien un installateur .exe '
                'et son empreinte SHA-256.'
            ))
