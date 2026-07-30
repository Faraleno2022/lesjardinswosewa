#!/usr/bin/env python
"""
Script de diagnostic pour vérifier la correspondance entre ClasseNote et ClasseEleve
Usage: python manage.py shell < diagnostic_classes.py
Ou: python diagnostic_classes.py (avec DJANGO_SETTINGS_MODULE configuré)
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote, MatiereNote, NoteMensuelle
from eleves.models import Classe as ClasseEleve, Eleve

def diagnostic_classes():
    print("=" * 80)
    print("DIAGNOSTIC DES CORRESPONDANCES CLASSES")
    print("=" * 80)
    
    # Récupérer toutes les ClasseNote actives
    classes_notes = ClasseNote.objects.filter(actif=True).order_by('ecole__nom', 'nom')
    
    problemes = []
    ok_count = 0
    
    for cn in classes_notes:
        print(f"\n--- ClasseNote: {cn.nom} (ID: {cn.id}) ---")
        print(f"    École: {cn.ecole.nom if cn.ecole else 'AUCUNE'}")
        print(f"    Année scolaire: {cn.annee_scolaire}")
        
        # Chercher la ClasseEleve correspondante
        classe_eleve = ClasseEleve.objects.filter(
            nom=cn.nom,
            annee_scolaire=cn.annee_scolaire,
            ecole=cn.ecole
        ).first()
        
        if classe_eleve:
            eleves_count = Eleve.objects.filter(classe=classe_eleve, statut='ACTIF').count()
            print(f"    ✅ ClasseEleve trouvée (ID: {classe_eleve.id})")
            print(f"    📚 Élèves actifs: {eleves_count}")
            ok_count += 1
        else:
            print(f"    ❌ AUCUNE ClasseEleve correspondante!")
            
            # Chercher des correspondances partielles
            print(f"    🔍 Recherche de correspondances partielles...")
            
            # Par nom similaire
            classes_similaires = ClasseEleve.objects.filter(
                nom__icontains=cn.nom.split()[0] if cn.nom else '',
                ecole=cn.ecole
            )
            
            if classes_similaires.exists():
                print(f"    📋 Classes similaires dans la même école:")
                for cs in classes_similaires[:5]:
                    print(f"       - '{cs.nom}' (ID: {cs.id}, Année: {cs.annee_scolaire})")
            
            # Par même école et année
            classes_meme_ecole = ClasseEleve.objects.filter(
                annee_scolaire=cn.annee_scolaire,
                ecole=cn.ecole
            )
            
            if classes_meme_ecole.exists():
                print(f"    📋 Toutes les classes de cette école pour {cn.annee_scolaire}:")
                for ce in classes_meme_ecole[:10]:
                    print(f"       - '{ce.nom}' (ID: {ce.id})")
            
            problemes.append({
                'classe_note': cn,
                'nom': cn.nom,
                'ecole': cn.ecole.nom if cn.ecole else 'AUCUNE',
                'annee': cn.annee_scolaire
            })
    
    # Résumé
    print("\n" + "=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"✅ Classes avec correspondance: {ok_count}")
    print(f"❌ Classes SANS correspondance: {len(problemes)}")
    
    if problemes:
        print("\n⚠️  CLASSES À CORRIGER:")
        for p in problemes:
            print(f"   - {p['nom']} ({p['ecole']}, {p['annee']})")
        
        print("\n💡 SOLUTIONS POSSIBLES:")
        print("   1. Vérifier que les noms des classes sont IDENTIQUES (majuscules, accents)")
        print("   2. Vérifier que l'année scolaire est la même")
        print("   3. Vérifier que l'école est correctement liée")
        print("   4. Créer la ClasseEleve manquante avec le même nom exact")

if __name__ == '__main__':
    diagnostic_classes()
