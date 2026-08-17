"""Sauvegarde l'installation locale : base + medias, vers plusieurs destinations."""
import os

from django.core.management.base import BaseCommand

from ecole_moderne import sauvegarde


class Command(BaseCommand):
    help = ("Cree une archive (base de donnees + media) et la depose sur chaque "
            "destination : dossier local, cloud synchronise, support amovible.")

    def add_arguments(self, parser):
        parser.add_argument(
            '--destination', action='append', dest='destinations', default=None,
            help='Dossier de destination (repetable). Par defaut : detection automatique.',
        )
        parser.add_argument(
            '--mot-de-passe', dest='mot_de_passe', default=None,
            help='Chiffre l archive (necessite pyzipper).',
        )
        parser.add_argument(
            '--lister', action='store_true',
            help='Affiche les destinations detectees et les archives presentes, sans sauvegarder.',
        )

    def handle(self, *args, **options):
        config = sauvegarde.charger_config()

        if options['lister']:
            self.stdout.write(self.style.MIGRATE_HEADING('Destinations detectees'))
            for cible in sauvegarde.destinations(config):
                etat = 'existe' if os.path.isdir(cible) else 'a creer'
                self.stdout.write(f'  - {cible}  [{etat}]')
            archives = sauvegarde.archives_disponibles(config)
            self.stdout.write(self.style.MIGRATE_HEADING(
                f'\nArchives disponibles ({len(archives)})'))
            for archive in archives[:20]:
                taille = archive['taille'] / (1024 * 1024)
                self.stdout.write(
                    f"  {archive['date']:%d/%m/%Y %H:%M}  {taille:6.1f} Mo  {archive['chemin']}")
            return

        rapport = sauvegarde.executer_sauvegarde(
            destinations_demandees=options['destinations'],
            mot_de_passe=options['mot_de_passe'],
            config=config,
        )

        for avertissement in rapport.avertissements:
            self.stdout.write(self.style.WARNING(f'Avertissement : {avertissement}'))
        for echec in rapport.destinations_ko:
            self.stdout.write(self.style.ERROR(f'Destination en echec : {echec}'))

        if not rapport.succes:
            self.stderr.write(self.style.ERROR(rapport.resume()))
            return

        for cible in rapport.destinations_ok:
            self.stdout.write(self.style.SUCCESS(f'Copie deposee : {cible}'))
        if rapport.supprimees:
            self.stdout.write(f'Rotation : {len(rapport.supprimees)} archive(s) ancienne(s) supprimee(s).')
        self.stdout.write(self.style.SUCCESS(rapport.resume()))
