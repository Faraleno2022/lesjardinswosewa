"""Restaure une archive de sauvegarde (base + medias) sur cette installation."""
from django.core.management.base import BaseCommand, CommandError

from ecole_moderne import sauvegarde


class Command(BaseCommand):
    help = ("Restaure une archive produite par 'sauvegarder'. Sans --archive, "
            "propose la plus recente trouvee sur les destinations connues.")

    def add_arguments(self, parser):
        parser.add_argument('--archive', default=None, help='Chemin du fichier .zip a restaurer.')
        parser.add_argument('--mot-de-passe', dest='mot_de_passe', default='',
                            help='Mot de passe si l archive est chiffree.')
        parser.add_argument('--confirmer', action='store_true',
                            help='Confirme le remplacement de la base et des medias actuels.')

    def handle(self, *args, **options):
        config = sauvegarde.charger_config()
        chemin = options['archive']

        if not chemin:
            disponibles = sauvegarde.archives_disponibles(config)
            if not disponibles:
                raise CommandError('Aucune archive trouvee sur les destinations connues.')
            chemin = disponibles[0]['chemin']
            self.stdout.write(f'Archive la plus recente : {chemin}')

        try:
            manifeste = sauvegarde.lire_manifeste(chemin, options['mot_de_passe'])
        except Exception as err:
            raise CommandError(f'Archive illisible : {err}')

        self.stdout.write(self.style.MIGRATE_HEADING('Contenu de l archive'))
        self.stdout.write(f"  Date      : {manifeste.get('date', '?')}")
        self.stdout.write(f"  Machine   : {manifeste.get('machine', '?')}")
        self.stdout.write(f"  Medias    : {(manifeste.get('media') or {}).get('nombre', '?')} fichier(s)")
        for cle, valeur in (manifeste.get('statistiques') or {}).items():
            self.stdout.write(f'  {cle:<9} : {valeur}')

        if not options['confirmer']:
            self.stdout.write(self.style.WARNING(
                '\nRien n a ete modifie. Relancez avec --confirmer pour restaurer '
                '(la base et les medias actuels seront mis de cote, horodates).'))
            return

        rapport = sauvegarde.restaurer(chemin, options['mot_de_passe'], config)
        for avertissement in rapport.avertissements:
            self.stdout.write(self.style.WARNING(f'Avertissement : {avertissement}'))
        if rapport.erreur:
            raise CommandError(rapport.erreur)
        self.stdout.write(self.style.SUCCESS(
            'Restauration terminee. Redemarrez MySchoolGN.'))
