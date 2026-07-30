from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Q
from eleves.models import Eleve, Classe, Ecole, _code_classe_from_nom_ou_niveau

class Command(BaseCommand):
    help = (
        "Resequencer les matricules par classe en appliquant le préfixe d'école. "
        "Par défaut en mode DRY-RUN (aucune écriture). Utilisez --apply pour appliquer."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--ecole-id", type=int, help="Limiter au périmètre d'une école (ID)")
        parser.add_argument("--classe-id", type=int, help="Limiter à une seule classe (ID)")
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Appliquer réellement les changements (par défaut: dry-run)"
        )

    def handle(self, *args, **options):
        ecole_id = options.get("ecole_id")
        classe_id = options.get("classe_id")
        apply = options.get("apply", False)

        classes = Classe.objects.all().select_related("ecole")
        if classe_id:
            classes = classes.filter(pk=classe_id)
        elif ecole_id:
            classes = classes.filter(ecole_id=ecole_id)

        total_classes = classes.count()
        if total_classes == 0:
            self.stdout.write(self.style.WARNING("Aucune classe ciblée."))
            return

        self.stdout.write(self.style.NOTICE(f"Ciblage: {total_classes} classe(s)"))
        modifications = 0

        # Parcours par classe et resequencage
        for classe in classes.order_by("ecole__nom", "niveau", "nom"):
            code = _code_classe_from_nom_ou_niveau(classe)
            if not code:
                code = f"CL{classe.id}"

            # Préfixe d'école (prioritaire: champ code_prefixe)
            prefix_ecole = (classe.ecole.code_prefixe or "").strip()
            if prefix_ecole:
                prefix_ecole = prefix_ecole.rstrip("/") + "/"

            # Ordre stable: par date_inscription puis par id
            eleves_qs = Eleve.objects.filter(classe=classe).order_by("date_inscription", "id")
            seq = 1
            for eleve in eleves_qs:
                nouveau = f"{prefix_ecole}{code}-{seq:03d}"
                ancien = eleve.matricule
                if ancien != nouveau:
                    if apply:
                        eleve.matricule = nouveau
                        eleve.save(update_fields=["matricule"])  # unique=True au modèle, collisions peu probables grâce à seq
                    self.stdout.write(f"{eleve.id}: {ancien} -> {nouveau}")
                    modifications += 1
                seq += 1

        if apply:
            self.stdout.write(self.style.SUCCESS(f"Terminé: {modifications} matricule(s) modifié(s)."))
        else:
            self.stdout.write(self.style.WARNING(f"DRY-RUN: {modifications} modification(s) potentielle(s). Utilisez --apply pour appliquer."))
