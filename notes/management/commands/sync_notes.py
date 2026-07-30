"""
Commande de gestion Django pour synchroniser les notes.

Usage:
    python manage.py sync_notes                    # Toutes les classes
    python manage.py sync_notes --annee 2025-2026  # Une année spécifique
    python manage.py sync_notes --classe 12        # Une classe spécifique (ID)
"""

from django.core.management.base import BaseCommand
from notes.signals import sync_all_notes_eleve_to_mensuelle
from notes.models import ClasseNote


class Command(BaseCommand):
    help = 'Synchronise les notes de NoteEleve vers NoteMensuelle'

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee',
            type=str,
            help='Année scolaire (ex: 2025-2026)',
        )
        parser.add_argument(
            '--classe',
            type=int,
            help='ID de la classe à synchroniser',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher ce qui serait fait sans exécuter',
        )

    def handle(self, *args, **options):
        annee = options.get('annee')
        classe_id = options.get('classe')
        dry_run = options.get('dry_run')
        
        self.stdout.write(self.style.NOTICE('=== SYNCHRONISATION DES NOTES ==='))
        self.stdout.write('')
        
        # Récupérer la classe si spécifiée
        classe_note = None
        if classe_id:
            try:
                classe_note = ClasseNote.objects.get(id=classe_id)
                self.stdout.write(f'Classe: {classe_note.nom}')
            except ClasseNote.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Classe ID {classe_id} non trouvée'))
                return
        
        if annee:
            self.stdout.write(f'Année scolaire: {annee}')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode dry-run: aucune modification'))
            # Afficher les statistiques sans modifier
            from notes.models import NoteEleve, NoteMensuelle, MatiereNote, Evaluation
            
            classes_qs = ClasseNote.objects.filter(actif=True)
            if classe_note:
                classes_qs = classes_qs.filter(id=classe_note.id)
            if annee:
                classes_qs = classes_qs.filter(annee_scolaire=annee)
            
            total_notes_eleve = 0
            total_notes_mensuelle = 0
            
            for cn in classes_qs:
                matieres = MatiereNote.objects.filter(classe=cn, actif=True)
                for mat in matieres:
                    evals = Evaluation.objects.filter(matiere=mat)
                    for ev in evals:
                        total_notes_eleve += NoteEleve.objects.filter(evaluation=ev).count()
                
                total_notes_mensuelle += NoteMensuelle.objects.filter(matiere__classe=cn).count()
            
            self.stdout.write(f'NoteEleve: {total_notes_eleve}')
            self.stdout.write(f'NoteMensuelle: {total_notes_mensuelle}')
            self.stdout.write(f'À synchroniser: ~{max(0, total_notes_eleve - total_notes_mensuelle)}')
            return
        
        # Exécuter la synchronisation
        self.stdout.write('')
        self.stdout.write('Synchronisation en cours...')
        
        stats = sync_all_notes_eleve_to_mensuelle(
            classe_note=classe_note,
            annee_scolaire=annee
        )
        
        # Afficher les résultats
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== RÉSULTATS ==='))
        self.stdout.write(f'Classes traitées: {stats["classes_traitees"]}')
        self.stdout.write(f'Notes créées: {stats["notes_creees"]}')
        self.stdout.write(f'Notes mises à jour: {stats["notes_mises_a_jour"]}')
        self.stdout.write(f'Notes ignorées (None): {stats["notes_ignorees"]}')
        
        if stats['erreurs']:
            self.stdout.write('')
            self.stdout.write(self.style.ERROR('Erreurs:'))
            for err in stats['erreurs']:
                self.stdout.write(f'  - {err}')
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('✅ Synchronisation terminée!'))
