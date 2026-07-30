#!/usr/bin/env python
"""
Script pour créer la classe élèves GRANDE SECTION et y ajouter des élèves
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Classe, Eleve, Ecole
from notes.models import ClasseNote
from django.contrib.auth.models import User
from datetime import date

def creer_classe_eleves_grande_section():
    """Crée la classe élèves GRANDE SECTION avec des élèves de test"""
    
    try:
        # Récupérer l'école
        ecole = Ecole.objects.first()
        print(f"École utilisée: {ecole.nom}")
        
        # Récupérer un utilisateur
        user = User.objects.first()
        
        # Vérifier si la classe existe déjà
        existing = Classe.objects.filter(
            nom="GRANDE SECTION",
            annee_scolaire="2025-2026",
            ecole=ecole
        ).first()
        
        if existing:
            print(f"⚠️  La classe élèves GRANDE SECTION existe déjà (ID: {existing.id})")
            return existing
        
        # Créer la classe élèves GRANDE SECTION
        classe_grande_section = Classe.objects.create(
            ecole=ecole,
            nom="GRANDE SECTION",
            annee_scolaire="2025-2026",
            niveau="MATERNELLE"
        )
        
        print(f"✅ Classe élèves GRANDE SECTION créée avec l'ID: {classe_grande_section.id}")
        
        # Créer des élèves de test
        eleves_data = [
            ("BAH", "YOUSSOUF", "01/01/2020", "GS-001"),
            ("CAMARA", "MARIAM", "15/03/2020", "GS-002"),
            ("DIALLO", "IBRAHIM", "10/06/2020", "GS-003"),
            ("TOURE", "FATOU", "25/09/2020", "GS-004"),
            ("BARRY", "MOHAMED", "05/12/2020", "GS-005"),
            ("SOUMAH", "AICHA", "18/02/2020", "GS-006"),
            ("BANGOURA", "OUMAR", "30/07/2020", "GS-007"),
            ("KANTE", "ADAMA", "12/11/2020", "GS-008"),
        ]
        
        print(f"\n👦 Création des élèves:")
        for nom, prenom, date_naiss, matricule in eleves_data:
            # Parser la date de naissance
            jour, mois, annee = date_naiss.split('/')
            date_naissance = date(int(annee), int(mois), int(jour))
            
            eleve = Eleve.objects.create(
                nom=nom,
                prenom=prenom,
                matricule=matricule,
                date_naissance=date_naissance,
                classe=classe_grande_section,
                statut='ACTIF',
                cree_par=user
            )
            print(f"   ✅ {prenom} {nom} ({matricule}) créé")
        
        print(f"\n🎉 GRANDE SECTION élèves créée avec succès!")
        print(f"   • ID de la classe: {classe_grande_section.id}")
        print(f"   • Nombre d'élèves: {len(eleves_data)}")
        
        return classe_grande_section
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 CRÉATION DE LA CLASSE ÉLÈVES GRANDE SECTION")
    print("="*60)
    creer_classe_eleves_grande_section()
