from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from paiements.models import EcheancierPaiement
from eleves.models import Eleve

# Nous réutilisons la logique centralisée dans les vues pour garantir une cohérence unique
from paiements.views import ensure_echeancier_for_eleve, _auto_validate_echeancier_for_eleve


class Command(BaseCommand):
    help = "Crée les échéanciers manquants pour tous les élèves et synchronise le statut (incl. EN_RETARD)."

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=0, help='Limiter le nombre d\'élèves traités (0 = tous)')
        parser.add_argument('--dry-run', action='store_true', help="Ne pas écrire en base, seulement simuler")

    def handle(self, *args, **options):
        limit = options.get('limit') or 0
        dry_run = bool(options.get('dry_run'))

        qs = Eleve.objects.select_related('classe', 'classe__ecole').all().order_by('id')
        total = qs.count()
        if limit > 0:
            qs = qs[:limit]
        processed = 0
        created = 0
        updated = 0

        self.stdout.write(self.style.NOTICE(f"Traitement de {qs.count()} élèves (sur {total}). Dry-run={dry_run}"))

        for eleve in qs:
            try:
                with transaction.atomic():
                    ech = getattr(eleve, 'echeancier', None)
                    if ech is None:
                        if dry_run:
                            created += 1
                        else:
                            ech = ensure_echeancier_for_eleve(eleve)
                            created += 1
                    # Synchroniser statut (PAYE_COMPLET / PAYE_PARTIEL / A_PAYER / EN_RETARD)
                    if not dry_run:
                        _auto_validate_echeancier_for_eleve(eleve)
                        updated += 1
                processed += 1
            except Exception as ex:
                self.stderr.write(self.style.ERROR(f"Erreur pour élève {getattr(eleve, 'matricule', eleve.id)}: {ex}"))
                continue

        self.stdout.write(self.style.SUCCESS(
            f"Terminé. Élèves traités={processed}, échéanciers créés={created}, statuts synchronisés={updated}."
        ))
