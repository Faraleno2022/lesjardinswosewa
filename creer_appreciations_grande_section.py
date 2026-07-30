#!/usr/bin/env python
"""
Script pour ajouter des appréciations par défaut aux élèves de la GRANDE SECTION
Créé le 21/01/2026 pour la classe GRANDE SECTION (ID: 76)
"""

import os
import django
import random

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import AppreciationMaternelle, MatiereNote, ClasseNote, BulletinMaternelle
from eleves.models import Eleve, Classe

def ajouter_appreciations_grande_section():
    """Ajoute des appréciations par défaut pour tous les élèves de la GRANDE SECTION"""
    
    # Paramètres pour la GRANDE SECTION
    CLASSE_ID = 76  # GRANDE SECTION
    TRIMESTRE = 'TRIMESTRE_1'
    ANNEE_SCOLAIRE = '2025-2026'
    
    # Mapping des classes spéciales
    mapping_classes = {
        61: 56,
        59: 8,
    }
    
    try:
        # Récupérer la classe de notes
        classe_note = ClasseNote.objects.get(id=CLASSE_ID)
        print(f"Classe trouvée: {classe_note.nom}")
        
        # Récupérer les matières
        matieres = MatiereNote.objects.filter(classe=classe_note, actif=True).order_by('nom')
        print(f"Matières trouvées: {matieres.count()}")
        for matiere in matieres:
            print(f"  - {matiere.nom} ({matiere.code})")
        
        # Récupérer la classe élèves
        if classe_note.id in mapping_classes:
            classe_eleves = Classe.objects.filter(id=mapping_classes[classe_note.id]).first()
        else:
            classe_eleves = Classe.objects.filter(
                nom=classe_note.nom,
                annee_scolaire=classe_note.annee_scolaire,
                ecole=classe_note.ecole
            ).first()
        
        if not classe_eleves:
            print("❌ Classe élèves non trouvée")
            return
        
        # Récupérer les élèves actifs
        eleves = Eleve.objects.filter(classe=classe_eleves, statut='ACTIF').order_by('nom')
        print(f"Élèves trouvés: {eleves.count()}")
        
        # Appréciations possibles avec poids réaliste pour grande section
        poids = ['A+', 'A', 'A', 'B+', 'B+', 'B', 'B', 'B-', 'C', 'D']
        
        # Statistiques
        total_appreciations_crees = 0
        total_bulletins_crees = 0
        
        # Traiter chaque élève
        for eleve in eleves:
            print(f"\n👦 Traitement de: {eleve}")
            
            # Vérifier si des appréciations existent déjà
            existing_appreciations = AppreciationMaternelle.objects.filter(
                eleve=eleve,
                trimestre=TRIMESTRE,
                annee_scolaire=ANNEE_SCOLAIRE
            )
            
            if existing_appreciations.exists():
                print(f"   ⚠️  {existing_appreciations.count()} appréciations existent déjà")
                continue
            
            # Créer les appréciations pour chaque matière
            eleve_appreciations = []
            for matiere in matieres:
                # Choisir une appréciation aléatoire mais réaliste
                appreciation_choisie = random.choice(poids)
                
                appreciation = AppreciationMaternelle.objects.create(
                    eleve=eleve,
                    matiere=matiere,
                    trimestre=TRIMESTRE,
                    annee_scolaire=ANNEE_SCOLAIRE,
                    appreciation=appreciation_choisie,
                    absent=False
                )
                eleve_appreciations.append(appreciation)
                print(f"   ✅ {matiere.nom}: {appreciation_choisie}")
            
            total_appreciations_crees += len(eleve_appreciations)
            
            # Créer ou mettre à jour le bulletin avec analyses et recommandations appropriées
            analyses_choisies = random.sample([
                'comprend', 'fixe_attention', 'pas_probleme_monitrice', 
                'pas_probleme_camarades', 'pas_probleme_famille', 'doue'
            ], k=3)
            
            recommandations_choisies = random.sample([
                'encourager_feliciter', 'suivre_domicile', 'gouter_sac',
                'aide_parents', 'amour_parental', 'epanoui'
            ], k=2)
            
            bulletin, created = BulletinMaternelle.objects.get_or_create(
                eleve=eleve,
                classe=classe_note,
                trimestre=TRIMESTRE,
                annee_scolaire=ANNEE_SCOLAIRE,
                defaults={
                    'analyses': analyses_choisies,
                    'recommandations': recommandations_choisies,
                    'appreciation_generale': f'Élève {eleve.prenom} fait des progrès remarquables en grande section.',
                    'signature_monitrice': False,
                    'signature_directeur': False,
                }
            )
            
            if created:
                total_bulletins_crees += 1
                print(f"   📋 Bulletin créé")
            else:
                print(f"   📋 Bulletin existant mis à jour")
        
        # Résumé final
        print(f"\n" + "="*60)
        print(f"🎉 OPÉRATION TERMINÉE AVEC SUCCÈS")
        print(f"="*60)
        print(f"📊 STATISTIQUES:")
        print(f"   • Élèves traités: {eleves.count()}")
        print(f"   • Matières par élève: {matieres.count()}")
        print(f"   • Appréciations créées: {total_appreciations_crees}")
        print(f"   • Bulletins créés: {total_bulletins_crees}")
        print(f"   • Trimestre: {TRIMESTRE}")
        print(f"   • Année scolaire: {ANNEE_SCOLAIRE}")
        print(f"\n✅ Les bulletins de grande section peuvent maintenant être générés!")
        print(f"📄 URL: http://127.0.0.1:8000/notes/maternelle/bulletins-classe-v2-pdf/?classe={CLASSE_ID}&trimestre={TRIMESTRE}")
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🚀 DÉMARRAGE - Ajout d'appréciations par défaut - GRANDE SECTION")
    print("="*60)
    ajouter_appreciations_grande_section()
