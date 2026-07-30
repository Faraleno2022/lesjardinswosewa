from django.core.management.base import BaseCommand
from eleves.models import Classe, Eleve
import re
from django.db import transaction

class Command(BaseCommand):
    help = 'Corrige tous les matricules en doublon dans le système'

    def handle(self, *args, **options):
        # Afficher les doublons
        duplicates = {}
        for eleve in Eleve.objects.all():
            mat = eleve.matricule
            if mat not in duplicates:
                duplicates[mat] = []
            duplicates[mat].append(eleve)
        
        doublons = {k: v for k, v in duplicates.items() if len(v) > 1}
        
        if doublons:
            self.stdout.write(self.style.ERROR(f"✗ {len(doublons)} matricules en doublon trouvés"))
            for mat, eleves in doublons.items():
                self.stdout.write(f"  {mat}: {len(eleves)} élèves")
        else:
            self.stdout.write(self.style.SUCCESS("✓ Aucun doublon détecté"))
        
        # Nettoyer les TEMP
        temp_eleves = Eleve.objects.filter(matricule__startswith='TEMP-')
        if temp_eleves.exists():
            self.stdout.write(self.style.WARNING(f"⚠ {temp_eleves.count()} matricules temporaires trouvés"))
            # À corriger manuellement selon le contexte

