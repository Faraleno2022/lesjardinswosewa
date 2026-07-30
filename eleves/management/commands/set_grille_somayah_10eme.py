from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal

from eleves.models import Ecole, GrilleTarifaire, Classe

class Command(BaseCommand):
    help = "Crée ou met à jour la GrilleTarifaire pour la 10ème année (COLLEGE_10) à SOMAYAH avec FI=30k, T1=710k, T2=610k, T3=480k pour l'année scolaire courante."

    def add_arguments(self, parser):
        parser.add_argument('--ecole', type=str, default='SOMAYAH', help='Nom (ou partie) de l\'école, ex: SOMAYAH')
        parser.add_argument('--annee', type=str, default=None, help='Année scolaire au format 2025-2026. Si omise, calculée selon la date du jour.')
        parser.add_argument('--fi', type=int, default=30000, help="Frais d'inscription (par défaut 30000)")
        parser.add_argument('--t1', type=int, default=710000, help='Montant 1ère tranche (par défaut 710000)')
        parser.add_argument('--t2', type=int, default=610000, help='Montant 2ème tranche (par défaut 610000)')
        parser.add_argument('--t3', type=int, default=480000, help='Montant 3ème tranche (par défaut 480000)')

    def handle(self, *args, **options):
        ecole_key = options['ecole']
        annee = options['annee']
        fi = Decimal(options['fi'])
        t1 = Decimal(options['t1'])
        t2 = Decimal(options['t2'])
        t3 = Decimal(options['t3'])

        # Déterminer l'année scolaire courante si non fournie
        if not annee:
            from datetime import date
            today = date.today()
            annee = f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}"

        # Rechercher l'école par correspondance partielle (insensible à la casse)
        ecoles = Ecole.objects.filter(nom__icontains=ecole_key)
        if not ecoles.exists():
            raise CommandError(f"Aucune école trouvée avec le motif: {ecole_key}")
        if ecoles.count() > 1:
            noms = ', '.join(ec.nom for ec in ecoles)
            self.stdout.write(self.style.WARNING(f"Plusieurs écoles correspondent: {noms}. La première sera utilisée."))
        ecole = ecoles.first()

        niveau = 'COLLEGE_10'  # 10ème année

        with transaction.atomic():
            grille, created = GrilleTarifaire.objects.get_or_create(
                ecole=ecole,
                niveau=niveau,
                annee_scolaire=annee,
                defaults={
                    'frais_inscription': fi,
                    'tranche_1': t1,
                    'tranche_2': t2,
                    'tranche_3': t3,
                }
            )
            if not created:
                grille.frais_inscription = fi
                grille.tranche_1 = t1
                grille.tranche_2 = t2
                grille.tranche_3 = t3
                grille.save()
                self.stdout.write(self.style.SUCCESS(
                    f"Grille mise à jour: {ecole.nom} - 10ème ({annee}) | FI={fi:,} T1={t1:,} T2={t2:,} T3={t3:,}"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"Grille créée: {ecole.nom} - 10ème ({annee}) | FI={fi:,} T1={t1:,} T2={t2:,} T3={t3:,}"
                ))

        self.stdout.write(self.style.SUCCESS("Opération terminée."))
