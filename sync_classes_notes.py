#!/usr/bin/env python
"""
Script pour synchroniser les ClasseEleve vers ClasseNote
Crée automatiquement les ClasseNote manquantes à partir des ClasseEleve existantes

Usage: python sync_classes_notes.py
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote
from eleves.models import Classe as ClasseEleve

def sync_classes():
    print("=" * 80)
    print("SYNCHRONISATION DES CLASSES")
    print("=" * 80)
    
    # Récupérer toutes les ClasseEleve
    classes_eleves = ClasseEleve.objects.all().order_by('ecole__nom', 'nom')
    
    created_count = 0
    existing_count = 0
    
    for ce in classes_eleves:
        # Vérifier si une ClasseNote correspondante existe
        classe_note_existante = ClasseNote.objects.filter(
            nom=ce.nom,
            annee_scolaire=ce.annee_scolaire,
            ecole=ce.ecole
        ).first()
        
        if classe_note_existante:
            print(f"✅ Existe déjà: {ce.nom} ({ce.ecole.nom if ce.ecole else 'Sans école'})")
            existing_count += 1
        else:
            # Créer la ClasseNote
            try:
                # Déterminer le niveau d'enseignement
                nom_lower = ce.nom.lower()
                if any(x in nom_lower for x in ['maternelle', 'petite', 'moyenne', 'grande section']):
                    niveau = 'MATERNELLE'
                elif any(x in nom_lower for x in ['1ère', '2ème', '3ème', '4ème', '5ème', '6ème']) and 'année' in nom_lower:
                    niveau = 'PRIMAIRE'
                elif any(x in nom_lower for x in ['7ème', '8ème', '9ème', '10ème']):
                    niveau = 'COLLEGE'
                elif any(x in nom_lower for x in ['11ème', '12ème', 'terminale']):
                    niveau = 'LYCEE'
                else:
                    niveau = 'SECONDAIRE'
                
                nouvelle_classe = ClasseNote.objects.create(
                    nom=ce.nom,
                    niveau=niveau,
                    niveau_enseignement=niveau,
                    annee_scolaire=ce.annee_scolaire,
                    ecole=ce.ecole,
                    actif=True
                )
                print(f"🆕 Créée: {ce.nom} ({ce.ecole.nom if ce.ecole else 'Sans école'}) - Niveau: {niveau}")
                created_count += 1
            except Exception as e:
                print(f"❌ Erreur pour {ce.nom}: {str(e)}")
    
    # Résumé
    print("\n" + "=" * 80)
    print("RÉSUMÉ")
    print("=" * 80)
    print(f"✅ Classes déjà existantes: {existing_count}")
    print(f"🆕 Classes créées: {created_count}")
    print(f"📊 Total traité: {existing_count + created_count}")
    
    if created_count > 0:
        print("\n💡 Les nouvelles classes sont maintenant disponibles dans le système de notes!")
        print("   N'oubliez pas de créer les matières pour chaque classe.")

if __name__ == '__main__':
    # Demander confirmation
    print("Ce script va créer les ClasseNote manquantes à partir des ClasseEleve.")
    reponse = input("Voulez-vous continuer ? (oui/non): ").strip().lower()
    
    if reponse in ['oui', 'o', 'yes', 'y']:
        sync_classes()
    else:
        print("Opération annulée.")
