from django.core.management.base import BaseCommand
from django.db.models import F, ExpressionWrapper, DecimalField, Q

from paiements.models import EcheancierPaiement
from paiements.notifications import send_retard_notification


class Command(BaseCommand):
    help = "Envoie des notifications de retard aux responsables (WhatsApp/SMS)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='N\'envoie pas, affiche seulement un résumé')
        parser.add_argument('--limit', type=int, default=500, help='Nombre maximum à traiter (défaut 500)')
        parser.add_argument('--ecole-id', type=int, help='Filtrer par ID école via eleve.classe.ecole_id')
        parser.add_argument('--classe-id', type=int, help='Filtrer par ID de classe')
        parser.add_argument('--min-solde', type=int, default=1, help='Solde minimal pour notifier (défaut > 0)')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        ecole_id = options.get('ecole_id')
        classe_id = options.get('classe_id')
        min_solde = options.get('min_solde') or 1

        solde_expr = (
            F('frais_inscription_du') + F('tranche_1_due') + F('tranche_2_due') + F('tranche_3_due')
            - (F('frais_inscription_paye') + F('tranche_1_payee') + F('tranche_2_payee') + F('tranche_3_payee'))
        )
        qs = (
            EcheancierPaiement.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole')
            .annotate(solde=ExpressionWrapper(solde_expr, output_field=DecimalField(max_digits=10, decimal_places=0)))
            .filter(solde__gte=min_solde)
        )
        if ecole_id:
            qs = qs.filter(eleve__classe__ecole_id=ecole_id)
        if classe_id:
            qs = qs.filter(eleve__classe_id=classe_id)

        total = qs.count()
        envoyes = 0
        self.stdout.write(self.style.NOTICE(f"Éligibles: {total}. Traitement max: {limit}. Dry-run: {dry_run}"))

        for ech in qs[:limit]:
            eleve = ech.eleve
            if dry_run:
                self.stdout.write(f"[DRY] {eleve.nom_complet} ({eleve.matricule}) - solde={ech.solde}")
                continue
            try:
                send_retard_notification(eleve, ech.solde)
                envoyes += 1
            except Exception as e:
                self.stderr.write(f"Échec envoi pour {eleve.nom_complet} ({eleve.matricule}): {e}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run terminé."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Notifications envoyées: {envoyes}/{min(total, limit)}"))
