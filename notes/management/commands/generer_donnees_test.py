"""
Commande pour générer des données de test pour le module Notes
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from notes.models import ClasseNote, MatiereNote, Evaluation, NoteEleve
from eleves.models import Eleve, Classe as ClasseEleve
from decimal import Decimal
import random


class Command(BaseCommand):
    help = 'Génère des données de test pour le module Notes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--classe',
            type=str,
            help='Nom de la classe (ex: "7ème Année")',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Supprimer toutes les données de notes existantes avant de générer',
        )

    def handle(self, *args, **options):
        classe_nom = options.get('classe')
        clear = options.get('clear')

        if clear:
            self.stdout.write(self.style.WARNING('🗑️  Suppression des données existantes...'))
            NoteEleve.objects.all().delete()
            Evaluation.objects.all().delete()
            MatiereNote.objects.all().delete()
            ClasseNote.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✅ Données supprimées'))

        # Récupérer les classes d'élèves
        if classe_nom:
            classes_eleves = ClasseEleve.objects.filter(nom__icontains=classe_nom)
        else:
            classes_eleves = ClasseEleve.objects.all()

        if not classes_eleves.exists():
            self.stdout.write(self.style.ERROR('❌ Aucune classe trouvée'))
            return

        self.stdout.write(self.style.SUCCESS(f'📚 Génération de données pour {classes_eleves.count()} classe(s)...'))

        with transaction.atomic():
            for classe_eleve in classes_eleves:
                self.generer_pour_classe(classe_eleve)

        self.stdout.write(self.style.SUCCESS('✅ Données de test générées avec succès!'))

    def generer_pour_classe(self, classe_eleve):
        """Génère les données pour une classe"""
        self.stdout.write(f'\n📖 Classe: {classe_eleve.nom}')

        # Créer ou récupérer la ClasseNote
        classe_note, created = ClasseNote.objects.get_or_create(
            nom=classe_eleve.nom,
            annee_scolaire=classe_eleve.annee_scolaire,
            defaults={
                'niveau': self.determiner_niveau(classe_eleve.nom),
                'ecole': classe_eleve.ecole if hasattr(classe_eleve, 'ecole') else None,
                'actif': True
            }
        )
        
        if created:
            self.stdout.write(f'  ✅ ClasseNote créée: {classe_note.nom}')
        else:
            self.stdout.write(f'  ℹ️  ClasseNote existante: {classe_note.nom}')

        # Créer les matières
        matieres_data = self.obtenir_matieres(classe_note.niveau)
        matieres = []
        
        for matiere_data in matieres_data:
            matiere, created = MatiereNote.objects.get_or_create(
                classe=classe_note,
                code=matiere_data['code'],
                defaults={
                    'nom': matiere_data['nom'],
                    'coefficient': matiere_data['coefficient'],
                    'actif': True
                }
            )
            matieres.append(matiere)
            if created:
                self.stdout.write(f'    ✅ Matière: {matiere.nom} (Coef: {matiere.coefficient})')

        # Créer les évaluations pour chaque période
        from datetime import date
        periodes = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        types_eval = [
            ('Devoir 1', 'DEVOIR', 1, 20),
            ('Devoir 2', 'DEVOIR', 1, 20),
            ('Composition', 'COMPOSITION', 2, 20),
        ]

        evaluations_par_periode = {}
        for periode in periodes:
            evaluations_par_periode[periode] = []
            for matiere in matieres:
                for titre_eval, type_eval, coef, note_sur in types_eval:
                    evaluation, created = Evaluation.objects.get_or_create(
                        matiere=matiere,
                        periode=periode,
                        titre=titre_eval,
                        defaults={
                            'type_evaluation': type_eval,
                            'coefficient': coef,
                            'note_sur': note_sur,
                            'date_evaluation': date.today()
                        }
                    )
                    evaluations_par_periode[periode].append(evaluation)
                    if created:
                        self.stdout.write(f'      ✅ Évaluation: {matiere.code} - {titre_eval} ({periode})')

        # Récupérer les élèves de la classe
        eleves = Eleve.objects.filter(classe=classe_eleve, statut='ACTIF')
        self.stdout.write(f'  👥 {eleves.count()} élève(s) trouvé(s)')

        # Générer des notes pour chaque élève
        for eleve in eleves:
            self.generer_notes_eleve(eleve, evaluations_par_periode)
            self.stdout.write(f'    ✅ Notes générées pour {eleve.nom} {eleve.prenom}')

    def determiner_niveau(self, nom_classe):
        """Détermine le niveau selon le nom de la classe"""
        nom_lower = nom_classe.lower()
        
        if '7' in nom_lower or 'septième' in nom_lower:
            return 'COLLEGE_7'
        elif '8' in nom_lower or 'huitième' in nom_lower:
            return 'COLLEGE_8'
        elif '9' in nom_lower or 'neuvième' in nom_lower:
            return 'COLLEGE_9'
        elif '10' in nom_lower or 'dixième' in nom_lower:
            return 'LYCEE_10'
        elif '11' in nom_lower or 'onzième' in nom_lower:
            return 'LYCEE_11'
        elif '12' in nom_lower or 'douzième' in nom_lower or 'terminale' in nom_lower:
            return 'LYCEE_12'
        else:
            return 'COLLEGE_7'  # Par défaut

    def obtenir_matieres(self, niveau):
        """Retourne les matières selon le niveau"""
        matieres_communes = [
            {'nom': 'FRANÇAIS', 'code': 'FR', 'coefficient': 4},
            {'nom': 'MATHEMATIQUE', 'code': 'MATH', 'coefficient': 4},
            {'nom': 'ANGLAIS', 'code': 'ANG', 'coefficient': 2},
            {'nom': 'HISTOIRE', 'code': 'HIST', 'coefficient': 2},
            {'nom': 'GEOGRAPHIE', 'code': 'GEO', 'coefficient': 2},
            {'nom': 'SCIENCES PHYSIQUES', 'code': 'PHY', 'coefficient': 2},
            {'nom': 'SCIENCES NATURELLES', 'code': 'SVT', 'coefficient': 2},
            {'nom': 'EPS', 'code': 'EPS', 'coefficient': 1},
            {'nom': 'ECM', 'code': 'ECM', 'coefficient': 1},
        ]

        if niveau in ['LYCEE_11', 'LYCEE_12']:
            # Ajouter des matières spécifiques au lycée
            matieres_communes.extend([
                {'nom': 'PHILOSOPHIE', 'code': 'PHILO', 'coefficient': 3},
                {'nom': 'CHIMIE', 'code': 'CHIM', 'coefficient': 2},
            ])

        return matieres_communes

    def generer_notes_eleve(self, eleve, evaluations_par_periode):
        """Génère des notes aléatoires pour un élève"""
        # Déterminer le niveau de l'élève (faible, moyen, bon, excellent)
        niveau_eleve = random.choices(
            ['faible', 'moyen', 'bon', 'excellent'],
            weights=[15, 40, 30, 15]
        )[0]

        # Plages de notes selon le niveau
        plages = {
            'faible': (5, 9),
            'moyen': (10, 13),
            'bon': (14, 16),
            'excellent': (17, 20)
        }
        
        min_note, max_note = plages[niveau_eleve]

        for periode, evaluations in evaluations_par_periode.items():
            for evaluation in evaluations:
                # Variation aléatoire autour du niveau de l'élève
                variation = random.uniform(-2, 2)
                note_base = random.uniform(min_note, max_note) + variation
                note_base = max(0, min(20, note_base))  # Limiter entre 0 et 20
                
                # Quelques absences aléatoires (5% de chance)
                absent = random.random() < 0.05
                
                NoteEleve.objects.get_or_create(
                    eleve=eleve,
                    evaluation=evaluation,
                    defaults={
                        'note': Decimal(str(round(note_base, 2))),
                        'absent': absent
                    }
                )
