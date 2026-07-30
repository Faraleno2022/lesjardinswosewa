"""
Commande pour initialiser les matières par défaut du chatbot
Usage: python manage.py init_chatbot
"""
from django.core.management.base import BaseCommand
from chatbot.models import Matiere


class Command(BaseCommand):
    help = 'Initialise les matières par défaut pour le chatbot éducatif'

    def handle(self, *args, **options):
        matieres_defaut = [
            {'nom': 'Mathématiques', 'icone': '📐', 'description': 'Algèbre, géométrie, analyse, statistiques', 'ordre': 1},
            {'nom': 'Français', 'icone': '📖', 'description': 'Grammaire, conjugaison, littérature, rédaction', 'ordre': 2},
            {'nom': 'Sciences Physiques', 'icone': '🔬', 'description': 'Physique et chimie', 'ordre': 3},
            {'nom': 'Sciences Naturelles', 'icone': '🌱', 'description': 'Biologie, SVT, environnement', 'ordre': 4},
            {'nom': 'Histoire-Géographie', 'icone': '🌍', 'description': 'Histoire et géographie', 'ordre': 5},
            {'nom': 'Anglais', 'icone': '🗣️', 'description': 'Langue anglaise', 'ordre': 6},
            {'nom': 'Philosophie', 'icone': '🏛️', 'description': 'Philosophie et éthique', 'ordre': 7},
            {'nom': 'Informatique', 'icone': '💻', 'description': 'Programmation, bureautique, TIC', 'ordre': 8},
            {'nom': 'Éducation Civique', 'icone': '⚖️', 'description': 'Citoyenneté et droits', 'ordre': 9},
            {'nom': 'Arts', 'icone': '🎨', 'description': 'Arts plastiques et visuels', 'ordre': 10},
        ]
        
        created_count = 0
        for matiere_data in matieres_defaut:
            matiere, created = Matiere.objects.get_or_create(
                nom=matiere_data['nom'],
                defaults={
                    'icone': matiere_data['icone'],
                    'description': matiere_data['description'],
                    'ordre': matiere_data['ordre']
                }
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"[OK] Matiere creee: {matiere.nom}"))
            else:
                self.stdout.write(f"  Matiere existante: {matiere.nom}")
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f"Terminé! {created_count} nouvelle(s) matière(s) créée(s)."))
        self.stdout.write(f"Total: {Matiere.objects.count()} matières")
