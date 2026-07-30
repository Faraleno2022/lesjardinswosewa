from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from decimal import Decimal
from datetime import date

from eleves.models import Ecole, GrilleTarifaire

# Mapping proposé à partir de la grille "Cycle / périodes"
LEVELS_DEFAULT = {
    # Maternelle
    'MATERNELLE':      {'fi': 30000, 't1': 650000, 't2': 500000, 't3': 350000},

    # Primaire 1-5
    'PRIMAIRE_1':     {'fi': 30000, 't1': 560000, 't2': 460000, 't3': 330000},
    'PRIMAIRE_2':     {'fi': 30000, 't1': 560000, 't2': 460000, 't3': 330000},
    'PRIMAIRE_3':     {'fi': 30000, 't1': 560000, 't2': 460000, 't3': 330000},
    'PRIMAIRE_4':     {'fi': 30000, 't1': 560000, 't2': 460000, 't3': 330000},
    'PRIMAIRE_5':     {'fi': 30000, 't1': 560000, 't2': 460000, 't3': 330000},

    # Primaire 6
    'PRIMAIRE_6':     {'fi': 30000, 't1': 710000, 't2': 610000, 't3': 480000},

    # Collège 7-9
    'COLLEGE_7':      {'fi': 30000, 't1': 660000, 't2': 660000, 't3': 300000},
    'COLLEGE_8':      {'fi': 30000, 't1': 660000, 't2': 660000, 't3': 300000},
    'COLLEGE_9':      {'fi': 30000, 't1': 660000, 't2': 660000, 't3': 300000},

    # Collège 10
    'COLLEGE_10':     {'fi': 30000, 't1': 710000, 't2': 610000, 't3': 480000},

    # Lycée 11-12
    'LYCEE_11':       {'fi': 30000, 't1': 760000, 't2': 590000, 't3': 360000},
    'LYCEE_12':       {'fi': 30000, 't1': 760000, 't2': 590000, 't3': 360000},
}

class Command(BaseCommand):
    help = "Crée/Mets à jour les GrillesTarifaires d'une école (par défaut SOMAYAH) pour l'année scolaire, selon le mapping par niveau. FI=30 000 par défaut."

    def add_arguments(self, parser):
        parser.add_argument('--ecole', type=str, default='SOMAYAH', help="Nom (ou motif) de l'école, ex: SOMAYAH ou SONFONIA")
        parser.add_argument('--annee', type=str, default=None, help="Année scolaire ex: 2025-2026. Si omise: calcul automatique selon la date du jour")
        parser.add_argument('--fi', type=int, default=30000, help="Frais d'inscription à appliquer (par défaut 30000) si override global souhaité")
        parser.add_argument('--dry-run', action='store_true', help='Affiche les changements sans enregistrer')

    def handle(self, *args, **opts):
        ecole_key = opts['ecole']
        annee = opts['annee']
        fi_override = opts['fi']
        dry = opts['dry_run']

        if not annee:
            today = date.today()
            annee = f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}"

        # Rechercher l'école par motif
        ecoles = Ecole.objects.filter(nom__icontains=ecole_key)
        if not ecoles.exists():
            raise CommandError(f"Aucune école trouvée avec le motif: {ecole_key}")
        if ecoles.count() > 1:
            noms = ', '.join(ec.nom for ec in ecoles)
            self.stdout.write(self.style.WARNING(f"Plusieurs écoles correspondent: {noms}. La première sera utilisée."))
        ecole = ecoles.first()

        levels = LEVELS_DEFAULT.copy()
        # Override FI global si demandé
        if fi_override is not None:
            for k in levels:
                levels[k]['fi'] = fi_override

        created_count = 0
        updated_count = 0
        for niveau, vals in levels.items():
            fi = Decimal(vals['fi'])
            t1 = Decimal(vals['t1'])
            t2 = Decimal(vals['t2'])
            t3 = Decimal(vals['t3'])

            if dry:
                self.stdout.write(f"[DRY] {ecole.nom} {niveau} {annee} -> FI={fi:,} T1={t1:,} T2={t2:,} T3={t3:,}")
                continue

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
                if created:
                    created_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Créée: {ecole.nom} - {niveau} ({annee}) | FI={fi:,} T1={t1:,} T2={t2:,} T3={t3:,}"
                    ))
                else:
                    grille.frais_inscription = fi
                    grille.tranche_1 = t1
                    grille.tranche_2 = t2
                    grille.tranche_3 = t3
                    grille.save()
                    updated_count += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"Mise à jour: {ecole.nom} - {niveau} ({annee}) | FI={fi:,} T1={t1:,} T2={t2:,} T3={t3:,}"
                    ))

        if not dry:
            self.stdout.write(self.style.SUCCESS(
                f"Terminé. {created_count} grilles créées, {updated_count} mises à jour pour {ecole.nom} ({annee})."
            ))
