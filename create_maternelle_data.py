import os
import django
import random
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve, Classe, Ecole
from notes.models import MatiereNote, EvaluationMaternelle, ClasseNote, NoteMaternelle
from utilisateurs.models import User

def create_maternelle_data():
    print("Création des données pour la maternelle...")
    
    # Créer ou récupérer une école
    ecole, created = Ecole.objects.get_or_create(
        nom="ÉCOLE TEST MATERNELLE",
        defaults={
            'adresse': 'Test Address',
            'telephone': '123456789',
            'email': 'test@ecole.com'
        }
    )
    if created:
        print(f"✅ École créée: {ecole.nom}")
    else:
        print(f"ℹ️  École existante: {ecole.nom}")
    
    # Créer une classe maternelle
    classe, created = Classe.objects.get_or_create(
        ecole=ecole,
        nom="MATERNELLE 1 - PETITE SECTION",
        defaults={
            'niveau': 'MATERNELLE',
            'capacite_max': 30,
            'annee_scolaire': '2025-2026',
            'code_matricule': 'MAT1'
        }
    )
    if created:
        print(f"✅ Classe créée: {classe.nom}")
    else:
        print(f"ℹ️  Classe existante: {classe.nom}")
    
    # Créer la ClasseNote associée
    classe_note, created = ClasseNote.objects.get_or_create(
        ecole=ecole,
        nom="MATERNELLE 1 - PETITE SECTION",
        defaults={
            'niveau': 'MATERNELLE',
            'niveau_enseignement': 'MATERNELLE',
            'annee_scolaire': '2025-2026'
        }
    )
    if created:
        print(f"✅ ClasseNote créée: {classe_note}")
    else:
        print(f"ℹ️  ClasseNote existante: {classe_note}")
    
    # Créer des matières pour la maternelle
    matieres_data = [
        {"nom": "Langage et Communication", "code": "LANG"},
        {"nom": "Découverte du Monde", "code": "DECO"},
        {"nom": "Arts Plastiques", "code": "ARTS"},
        {"nom": "Éveil Corporel", "code": "EVEIL"},
        {"nom": "Mathématiques", "code": "MATH"},
        {"nom": "Musique et Chanson", "code": "MUSIQUE"},
    ]
    
    matieres = []
    for matiere_data in matieres_data:
        matiere, created = MatiereNote.objects.get_or_create(
            classe=classe_note,
            nom=matiere_data["nom"],
            defaults={
                'code': matiere_data["code"],
                'coefficient': 1.0
            }
        )
        matieres.append(matiere)
        if created:
            print(f"✅ Matière créée: {matiere.nom}")
        else:
            print(f"ℹ️  Matière existante: {matiere.nom}")
    
    # Créer des élèves
    prenoms = ["Awa", "Mamadou", "Fatoumata", "Boubacar", "Aminata", "Ibrahim", "Mariam", "Oumar", "Khadija", "Seydou"]
    noms = ["Diallo", "Bâ", "Camara", "Sow", "Konaté", "Cissé", "Diarra", "Touré"]
    
    for i in range(10):
        nom = random.choice(noms)
        prenom = random.choice(prenoms)
        matricule = f"MAT1-{i+1:03d}"
        
        eleve, created = Eleve.objects.get_or_create(
            matricule=matricule,
            defaults={
                'nom': nom,
                'prenom': prenom,
                'date_naissance': date(2019, random.randint(1, 12), random.randint(1, 28)),
                'sexe': random.choice(['M', 'F']),
                'classe': classe,
                'statut': 'ACTIF'
            }
        )
        if created:
            print(f"✅ Élève créé: {eleve.nom} {eleve.prenom} ({eleve.matricule})")
        else:
            print(f"ℹ️  Élève existant: {eleve.nom} {eleve.prenom}")
    
    # Créer des évaluations pour chaque élève
    eleves = Eleve.objects.filter(classe=classe)
    trimestres = ["TRIMESTRE_1", "TRIMESTRE_2", "TRIMESTRE_3"]
    
    for eleve in eleves:
        for trimestre in trimestres:
            # Créer l'évaluation principale
            evaluation, created = EvaluationMaternelle.objects.get_or_create(
                eleve=eleve,
                classe=classe_note,
                trimestre=trimestre,
                defaults={
                    'annee_scolaire': '2025-2026'
                }
            )
            if created:
                print(f"✅ Évaluation créée: {eleve.prenom} - {trimestre}")
            
            # Créer les notes par matière
            for matiere in matieres:
                # Lettres aléatoires avec pondération
                lettres_poids = [
                    ('A+', 0.1),  # 10%
                    ('A', 0.15),  # 15%
                    ('B+', 0.25), # 25%
                    ('B', 0.25),  # 25%
                    ('B-', 0.15), # 15%
                    ('C', 0.08),  # 8%
                    ('D', 0.02)   # 2%
                ]
                
                lettre = random.choices(
                    [l[0] for l in lettres_poids],
                    weights=[l[1] for l in lettres_poids]
                )[0]
                
                note_maternelle, created = NoteMaternelle.objects.get_or_create(
                    evaluation=evaluation,
                    matiere=matiere,
                    defaults={
                        'lettre': lettre
                    }
                )
                if created:
                    print(f"✅ Note créée: {eleve.prenom} - {matiere.nom} - {lettre}")
    
    # Créer l'appréciation générale pour chaque élève
    for eleve in eleves:
        for trimestre in trimestres:
            # Récupérer l'évaluation
            try:
                evaluation = EvaluationMaternelle.objects.get(
                    eleve=eleve, 
                    trimestre=trimestre
                )
                
                # Compter les lettres
                compteur = {}
                for note in evaluation.notes_matieres.all():
                    compteur[note.lettre] = compteur.get(note.lettre, 0) + 1
                
                # Déterminer la lettre générale (la plus fréquente)
                if compteur:
                    lettre_generale = max(compteur, key=compteur.get)
                    # Mettre à jour l'évaluation avec cette lettre générale
                    # (Note: je ne vois pas de champ lettre_generale dans EvaluationMaternelle)
                    print(f"✅ Appréciation générale: {eleve.prenom} - {trimestre} - {lettre_generale}")
                
            except EvaluationMaternelle.DoesNotExist:
                pass
    
    print("\n🎉 Données de test créées avec succès!")
    print(f"📊 {classe.nom} - {classe.eleves_set.count()} élèves")
    print(f"📚 {len(matieres)} matières")
    print(f"📝 {NoteMaternelle.objects.filter(evaluation__classe=classe_note).count()} notes")
    
    print("\n🔍 Pour tester:")
    print("1. Connectez-vous avec: TOLNO / motdepasse")
    print("2. Allez dans: Notes → Évaluations → Saisie Élève Maternelle")
    print("3. Sélectionnez un élève et une période")
    print("4. Générez le bulletin PDF")

if __name__ == "__main__":
    create_maternelle_data()
