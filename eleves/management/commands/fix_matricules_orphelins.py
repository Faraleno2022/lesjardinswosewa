# Créer le fichier: eleves/management/commands/fix_matricules_orphelins.py

from django.core.management.base import BaseCommand
from eleves.models import Eleve, Classe
import re

class Command(BaseCommand):
    help = 'Corrige les élèves sans matricule et les matricules en doublon'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("\n=== CORRECTION DES MATRICULES ORPHELINS ===\n"))
        
        # Étape 1: Trouver et corriger les élèves sans matricule
        orphelins = Eleve.objects.filter(matricule__in=['', None])
        
        if orphelins.exists():
            self.stdout.write(self.style.WARNING(f"⚠️  Trouvé {orphelins.count()} élèves sans matricule"))
            
            for eleve in orphelins:
                self.stdout.write(f"   - ID {eleve.id}: {eleve.prenom} {eleve.nom} (classe: {eleve.classe})")
                
                # Si l'élève a une classe, assigner un matricule basé sur sa classe
                if eleve.classe:
                    # Trouver le prochain numéro disponible
                    classe_nom = eleve.classe.nom
                    
                    # Extraire un code depuis le nom de la classe
                    code = self._extraire_code_classe(classe_nom)
                    
                    # Trouver le prochain numéro
                    next_num = self._trouver_prochain_numero(code)
                    
                    nouveau_mat = f"{code}-{next_num:03d}"
                    eleve.matricule = nouveau_mat
                    eleve.save(update_fields=['matricule'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(f"   ✓ Assigné: {nouveau_mat}")
                    )
                else:
                    # Pas de classe, assigner un matricule générique
                    eleve.matricule = f"ORPHELIN-{eleve.id}"
                    eleve.save(update_fields=['matricule'])
                    self.stdout.write(
                        self.style.WARNING(f"   ⚠️  Assigné provisoire: ORPHELIN-{eleve.id}")
                    )
        else:
            self.stdout.write(self.style.SUCCESS("✓ Aucun élève sans matricule"))
        
        self.stdout.write("")
        
        # Étape 2: Vérifier et corriger les doublons
        doublons = {}
        for eleve in Eleve.objects.all():
            mat = eleve.matricule
            if mat not in doublons:
                doublons[mat] = []
            doublons[mat].append(eleve)
        
        doublons_reels = {k: v for k, v in doublons.items() if len(v) > 1}
        
        if doublons_reels:
            self.stdout.write(self.style.ERROR(f"❌ Trouvé {len(doublons_reels)} matricules en doublon"))
            
            for mat, eleves in doublons_reels.items():
                self.stdout.write(f"\n   {mat}: {len(eleves)} élèves")
                for e in eleves:
                    self.stdout.write(f"      - ID {e.id}: {e.prenom} {e.nom}")
        else:
            self.stdout.write(self.style.SUCCESS("✓ Aucun doublon détecté"))
        
        self.stdout.write(self.style.SUCCESS("\n=== CORRECTION TERMINÉE ===\n"))
    
    def _extraire_code_classe(self, nom_classe):
        """Extrait un code court du nom de la classe"""
        # Chercher un pattern du style "CL10", "L11SC", etc.
        match = re.search(r'([A-Z0-9]+)', nom_classe)
        if match:
            return match.group(1)
        return "NC"  # "No Class"
    
    def _trouver_prochain_numero(self, code):
        """Trouve le prochain numéro disponible pour un code"""
        pattern = f"^{re.escape(code)}-(\d+)$"
        
        existing = Eleve.objects.filter(matricule__regex=pattern).values_list('matricule', flat=True)
        
        numbers = []
        for mat in existing:
            match = re.search(r'-(\d+)$', mat)
            if match:
                numbers.append(int(match.group(1)))
        
        if numbers:
            return max(numbers) + 1
        return 1
