from django.core.management.base import BaseCommand
from paiements.models import TypePaiement


class Command(BaseCommand):
    help = "Créer les types de paiement pour Réinscription"

    def handle(self, *args, **options):
        types = [
            {"nom": "Réinscription", "description": "Frais de réinscription uniquement"},
            {"nom": "Réinscription + Tranche 1", "description": "Réinscription + 1ère tranche"},
            {"nom": "Réinscription + Tranche 1 + Tranche 2", "description": "Réinscription + 1ère + 2ème tranches"},
            {"nom": "Réinscription + Annuel", "description": "Réinscription + total scolarité"},
        ]
        created = 0
        for t in types:
            obj, was_created = TypePaiement.objects.get_or_create(
                nom=t["nom"],
                defaults={"description": t["description"], "actif": True}
            )
            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"Cree: {obj.nom}"))
            else:
                self.stdout.write(self.style.WARNING(f"Existe deja: {obj.nom}"))
        self.stdout.write(self.style.SUCCESS(f"{created} type(s) crees."))
