#!/usr/bin/env python
"""
Script pour créer la classe GRANDE SECTION manquante
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote, MatiereNote
from eleves.models import Ecole
from django.contrib.auth.models import User

def creer_grande_section():
    """Crée la classe GRANDE SECTION avec ses matières"""
    
    try:
        # Récupérer l'école (utiliser la première disponible)
        ecole = Ecole.objects.first()
        if not ecole:
            print("❌ Aucune école trouvée dans la base de données")
            return
        
        print(f"École utilisée: {ecole.nom}")
        
        # Récupérer un utilisateur pour le created_by
        user = User.objects.first()
        
        # Vérifier si la classe existe déjà
        existing = ClasseNote.objects.filter(
            nom="GRANDE SECTION",
            annee_scolaire="2025-2026",
            ecole=ecole
        ).first()
        
        if existing:
            print(f"⚠️  La classe GRANDE SECTION existe déjà (ID: {existing.id})")
            return existing
        
        # Créer la classe GRANDE SECTION
        classe_grande_section = ClasseNote.objects.create(
            ecole=ecole,
            nom="GRANDE SECTION",
            niveau="MATERNELLE",
            niveau_enseignement="MATERNELLE",
            annee_scolaire="2025-2026",
            effectif=0,
            description="Classe de Grande Section - Maternelle",
            actif=True,
            cree_par=user
        )
        
        print(f"✅ Classe GRANDE SECTION créée avec l'ID: {classe_grande_section.id}")
        
        # Créer les matières pour la grande section
        matieres_data = [
            ("Calcul", "CALC"),
            ("Dessin", "DESS"),
            ("Écriture", "ECR"),
            ("Jeux éducatifs", "JEUX"),
            ("Langage", "LANG"),
            ("Lecture", "LEC"),
            ("Psychomotricité", "PSYCH"),
            ("Récitation/Chant", "REC"),
        ]
        
        print(f"\n📚 Création des matières:")
        for nom_matiere, code in matieres_data:
            matiere = MatiereNote.objects.create(
                classe=classe_grande_section,
                nom=nom_matiere,
                code=code,
                coefficient=1.0,
                description=f"Matière de {nom_matiere} pour Grande Section",
                actif=True,
                cree_par=user
            )
            print(f"   ✅ {nom_matiere} ({code}) créée")
        
        print(f"\n🎉 GRANDE SECTION créée avec succès!")
        print(f"   • ID de la classe: {classe_grande_section.id}")
        print(f"   • Nombre de matières: {len(matières_data)}")
        print(f"   • URL des bulletins: http://127.0.0.1:8000/notes/maternelle/bulletins-classe-v2-pdf/?classe={classe_grande_section.id}&trimestre=TRIMESTRE_1")
        
        return classe_grande_section
        
    except Exception as e:
        print(f"❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 CRÉATION DE LA CLASSE GRANDE SECTION")
    print("="*50)
    creer_grande_section()
