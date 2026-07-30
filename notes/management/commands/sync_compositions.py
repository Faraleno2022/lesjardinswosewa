"""
Commande de gestion pour synchroniser les notes d'évaluation trimestrielles/semestrielles
vers CompositionNote.

Usage:
    python manage.py sync_compositions
    python manage.py sync_compositions --annee 2025-2026
    python manage.py sync_compositions --classe 33
    python manage.py sync_compositions --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from notes.models import ClasseNote, MatiereNote, Evaluation, NoteEleve, CompositionNote


class Command(BaseCommand):
    help = 'Synchronise les notes d\'évaluation trimestrielles/semestrielles vers CompositionNote'

    def add_arguments(self, parser):
        parser.add_argument(
            '--annee',
            type=str,
            help='Année scolaire spécifique (ex: 2025-2026)'
        )
        parser.add_argument(
            '--classe',
            type=int,
            help='ID de la ClasseNote spécifique'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche ce qui serait fait sans modifier la base'
        )

    def handle(self, *args, **options):
        annee = options.get('annee')
        classe_id = options.get('classe')
        dry_run = options.get('dry_run', False)

        self.stdout.write(self.style.NOTICE('Synchronisation des notes de composition...'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN: aucune modification ne sera effectuée'))

        # Définir les périodes trimestrielles et semestrielles
        periodes_composition = [
            'TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3',
            'SEMESTRE_1', 'SEMESTRE_2'
        ]

        # Filtrer les classes
        classes_qs = ClasseNote.objects.filter(actif=True)
        if classe_id:
            classes_qs = classes_qs.filter(id=classe_id)
        if annee:
            classes_qs = classes_qs.filter(annee_scolaire=annee)

        stats = {
            'classes_traitees': 0,
            'notes_creees': 0,
            'notes_mises_a_jour': 0,
            'notes_ignorees': 0,
            'erreurs': []
        }

        for classe_note in classes_qs:
            try:
                self.stdout.write(f"  Traitement: {classe_note.nom} ({classe_note.annee_scolaire})")
                
                with transaction.atomic():
                    matieres = MatiereNote.objects.filter(classe=classe_note, actif=True)
                    
                    for matiere in matieres:
                        evaluations = Evaluation.objects.filter(
                            matiere=matiere,
                            periode__in=periodes_composition
                        )
                        
                        for evaluation in evaluations:
                            notes_eleve = NoteEleve.objects.filter(
                                evaluation=evaluation
                            ).select_related('eleve')
                            
                            for ne in notes_eleve:
                                if ne.note is None and not ne.absent:
                                    stats['notes_ignorees'] += 1
                                    continue
                                
                                note_value = ne.note if ne.note is not None else 0
                                
                                if not dry_run:
                                    compo, created = CompositionNote.objects.update_or_create(
                                        eleve=ne.eleve,
                                        matiere=matiere,
                                        periode=evaluation.periode,
                                        annee_scolaire=classe_note.annee_scolaire,
                                        defaults={
                                            'note': note_value,
                                            'absent': ne.absent,
                                            'cree_par': ne.cree_par
                                        }
                                    )
                                    
                                    if created:
                                        stats['notes_creees'] += 1
                                    else:
                                        stats['notes_mises_a_jour'] += 1
                                else:
                                    # En mode dry-run, juste compter
                                    existing = CompositionNote.objects.filter(
                                        eleve=ne.eleve,
                                        matiere=matiere,
                                        periode=evaluation.periode,
                                        annee_scolaire=classe_note.annee_scolaire
                                    ).exists()
                                    
                                    if existing:
                                        stats['notes_mises_a_jour'] += 1
                                    else:
                                        stats['notes_creees'] += 1
                    
                    stats['classes_traitees'] += 1
                    
            except Exception as e:
                stats['erreurs'].append(f"{classe_note.nom}: {str(e)}")
                self.stdout.write(self.style.ERROR(f"    Erreur: {e}"))

        # Afficher les statistiques
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== RÉSULTATS ==='))
        self.stdout.write(f"  Classes traitées: {stats['classes_traitees']}")
        self.stdout.write(f"  Notes créées: {stats['notes_creees']}")
        self.stdout.write(f"  Notes mises à jour: {stats['notes_mises_a_jour']}")
        self.stdout.write(f"  Notes ignorées (vides): {stats['notes_ignorees']}")
        
        if stats['erreurs']:
            self.stdout.write(self.style.ERROR(f"  Erreurs: {len(stats['erreurs'])}"))
            for err in stats['erreurs']:
                self.stdout.write(self.style.ERROR(f"    - {err}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nMode DRY-RUN: aucune modification effectuée'))
        else:
            self.stdout.write(self.style.SUCCESS('\nSynchronisation terminée!'))
