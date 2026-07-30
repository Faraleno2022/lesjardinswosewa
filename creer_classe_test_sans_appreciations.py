#!/usr/bin/env python
"""
Script pour tester l'affichage des activités sans appréciations
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote, MatiereNote
from eleves.models import Classe, Eleve
from django.contrib.auth.models import User
from datetime import date

def creer_classe_test_sans_appreciations():
    """Crée une classe test sans appréciations pour tester l'affichage"""
    
    try:
        # Récupérer l'école et utilisateur
        from eleves.models import Ecole
        ecole = Ecole.objects.first()
        user = User.objects.first()
        
        # Créer une classe de notes MOYENNE SECTION
        classe_note = ClasseNote.objects.create(
            ecole=ecole,
            nom="MOYENNE SECTION",
            niveau="MATERNELLE",
            niveau_enseignement="MATERNELLE",
            annee_scolaire="2025-2026",
            effectif=0,
            description="Classe test sans appréciations",
            actif=True,
            cree_par=user
        )
        
        print(f"✅ Classe MOYENNE SECTION créée (ID: {classe_note.id})")
        
        # Créer quelques matières
        matieres_data = [
            ("Mathématiques", "MATH"),
            ("Français", "FR"),
            ("Sciences", "SCI"),
        ]
        
        for nom, code in matieres_data:
            MatiereNote.objects.create(
                classe=classe_note,
                nom=nom,
                code=code,
                coefficient=1.0,
                description=f"Matière de {nom}",
                actif=True,
                cree_par=user
            )
        
        # Créer une classe élèves
        classe_eleves = Classe.objects.create(
            ecole=ecole,
            nom="MOYENNE SECTION",
            annee_scolaire="2025-2026",
            niveau="MATERNELLE"
        )
        
        print(f"✅ Classe élèves MOYENNE SECTION créée (ID: {classe_eleves.id})")
        
        # Ajouter un élève test
        eleve = Eleve.objects.create(
            nom="TEST",
            prenom="ELEVE",
            matricule="MS-001",
            date_naissance=date(2019, 5, 15),
            classe=classe_eleves,
            statut='ACTIF',
            cree_par=user
        )
        
        print(f"✅ Élève test créé: {eleve.prenom} {eleve.nom}")
        
        print(f"\n🎉 Classe test créée!")
        print(f"   • URL de test: http://127.0.0.1:8000/notes/maternelle/bulletins-classe-v2-pdf/?classe={classe_note.id}&trimestre=TRIMESTRE_1")
        print(f"   • Les activités devraient s'afficher avec des cases vides")
        
        return classe_note.id
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🧪 CRÉATION CLASSE TEST SANS APPRÉCIATIONS")
    print("="*50)
    creer_classe_test_sans_appreciations()
