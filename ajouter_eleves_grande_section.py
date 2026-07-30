#!/usr/bin/env python
"""
Script pour ajouter des élèves à la GRANDE SECTION
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve, Classe
from django.contrib.auth.models import User
from datetime import date

def ajouter_eleves_grande_section():
    """Ajoute des élèves à la classe GRANDE SECTION"""
    
    try:
        # Récupérer la classe GRANDE SECTION
        classe_grande_section = Classe.objects.get(id=61)
        print(f"Classe: {classe_grande_section.nom} (ID: {classe_grande_section.id})")
        
        # Récupérer un utilisateur
        user = User.objects.first()
        
        # Données des élèves
        eleves_data = [
            ("BAH", "YOUSSOUF", "01/01/2020", "GS-001"),
            ("CAMARA", "MARIAM", "15/03/2020", "GS-002"),
            ("DIALLO", "IBRAHIM", "10/06/2020", "GS-003"),
            ("TOURE", "FATOU", "25/09/2020", "GS-004"),
            ("BARRY", "MOHAMED", "05/12/2020", "GS-005"),
        ]
        
        print(f"\n👦 Ajout des élèves:")
        for nom, prenom, date_naiss, matricule in eleves_data:
            # Parser la date de naissance
            jour, mois, annee = date_naiss.split('/')
            date_naissance = date(int(annee), int(mois), int(jour))
            
            # Vérifier si l'élève existe déjà
            existing = Eleve.objects.filter(matricule=matricule).first()
            if existing:
                print(f"   ⚠️  {prenom} {nom} ({matricule}) existe déjà")
                continue
            
            # Créer l'élève
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
        
        # Vérifier le résultat
        total_eleves = Eleve.objects.filter(classe=classe_grande_section, statut='ACTIF').count()
        print(f"\n🎉 Total d'élèves actifs dans la classe: {total_eleves}")
        
        return total_eleves
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return 0

if __name__ == "__main__":
    print("🚀 AJOUT D'ÉLÈVES À LA GRANDE SECTION")
    print("="*50)
    ajouter_eleves_grande_section()
