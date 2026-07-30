"""
Signaux Django pour la synchronisation automatique des notes.

Ce module assure que les notes saisies via NoteEleve (Evaluation) sont
automatiquement synchronisées vers NoteMensuelle pour les bulletins.

PROBLÈME RÉSOLU:
- Les notes saisies via le système d'évaluations n'apparaissaient pas dans les bulletins
- Car les bulletins cherchent dans NoteMensuelle, pas dans NoteEleve

SOLUTION:
- Signal post_save sur NoteEleve qui crée/met à jour NoteMensuelle automatiquement
- Signal post_delete sur NoteEleve qui supprime NoteMensuelle correspondante
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender='notes.NoteEleve')
def sync_note_eleve_to_mensuelle(sender, instance, created, **kwargs):
    """
    Synchronise automatiquement une NoteEleve vers NoteMensuelle ou CompositionNote.
    
    Déclenché à chaque sauvegarde d'une NoteEleve.
    Crée ou met à jour la NoteMensuelle (périodes mensuelles) ou CompositionNote (trimestrielles/semestrielles).
    """
    from .models import NoteMensuelle, CompositionNote, NoteEleve
    
    try:
        # Récupérer les informations de l'évaluation
        evaluation = instance.evaluation
        matiere = evaluation.matiere
        classe_note = matiere.classe
        periode = evaluation.periode
        
        # Définir les types de périodes
        periodes_mensuelles = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 
                               'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN']
        periodes_trimestrielles = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        periodes_semestrielles = ['SEMESTRE_1', 'SEMESTRE_2']
        
        if periode in periodes_mensuelles:
            # Ignorer si la note est None (sauf si absent)
            if instance.note is None and not instance.absent:
                return
            
            # Créer ou mettre à jour NoteMensuelle
            note_value = instance.note if instance.note is not None else 0
            
            NoteMensuelle.objects.update_or_create(
                eleve=instance.eleve,
                matiere=matiere,
                mois=periode,
                annee_scolaire=classe_note.annee_scolaire,
                defaults={
                    'note': note_value,
                    'absent': instance.absent,
                    'cree_par': instance.cree_par
                }
            )
            
            # Invalider tous les caches liés (rangs + classements)
            from .utils_rangs import invalider_cache_rangs
            invalider_cache_rangs(classe_note, periode)
            
            logger.debug(f"Note mensuelle synchronisée: {instance.eleve} - {matiere.nom} - {periode}")
        
        elif periode in periodes_trimestrielles or periode in periodes_semestrielles:
            # Ignorer si la note est None (sauf si absent)
            if instance.note is None and not instance.absent:
                return
            
            # Créer ou mettre à jour CompositionNote
            note_value = instance.note if instance.note is not None else 0
            
            CompositionNote.objects.update_or_create(
                eleve=instance.eleve,
                matiere=matiere,
                periode=periode,
                annee_scolaire=classe_note.annee_scolaire,
                defaults={
                    'note': note_value,
                    'absent': instance.absent,
                    'cree_par': instance.cree_par
                }
            )
            
            # Invalider tous les caches liés (rangs + classements)
            from .utils_rangs import invalider_cache_rangs
            invalider_cache_rangs(classe_note, periode)
            
            logger.debug(f"Note composition synchronisée: {instance.eleve} - {matiere.nom} - {periode}")
            
    except Exception as e:
        logger.error(f"Erreur sync NoteEleve -> NoteMensuelle/CompositionNote: {e}")


@receiver(post_delete, sender='notes.NoteEleve')
def delete_note_mensuelle_on_note_eleve_delete(sender, instance, **kwargs):
    """
    Supprime la NoteMensuelle ou CompositionNote correspondante quand une NoteEleve est supprimée.
    """
    from .models import NoteMensuelle, CompositionNote, NoteEleve
    
    try:
        evaluation = instance.evaluation
        matiere = evaluation.matiere
        classe_note = matiere.classe
        periode = evaluation.periode
        
        periodes_mensuelles = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 
                               'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN']
        periodes_trimestrielles = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        periodes_semestrielles = ['SEMESTRE_1', 'SEMESTRE_2']
        
        # Vérifier s'il y a d'autres évaluations pour cette période
        autres_notes = NoteEleve.objects.filter(
            eleve=instance.eleve,
            evaluation__matiere=matiere,
            evaluation__periode=periode
        ).exclude(id=instance.id).exists()
        
        # Ne supprimer que s'il n'y a pas d'autres notes
        if not autres_notes:
            if periode in periodes_mensuelles:
                NoteMensuelle.objects.filter(
                    eleve=instance.eleve,
                    matiere=matiere,
                    mois=periode,
                    annee_scolaire=classe_note.annee_scolaire
                ).delete()
                logger.debug(f"NoteMensuelle supprimée: {instance.eleve} - {matiere.nom} - {periode}")
            
            elif periode in periodes_trimestrielles or periode in periodes_semestrielles:
                CompositionNote.objects.filter(
                    eleve=instance.eleve,
                    matiere=matiere,
                    periode=periode,
                    annee_scolaire=classe_note.annee_scolaire
                ).delete()
                logger.debug(f"CompositionNote supprimée: {instance.eleve} - {matiere.nom} - {periode}")
            
            # Invalider tous les caches liés
            from .utils_rangs import invalider_cache_rangs
            invalider_cache_rangs(classe_note, periode)
                
    except Exception as e:
        logger.error(f"Erreur suppression NoteMensuelle/CompositionNote: {e}")


def sync_all_notes_eleve_to_mensuelle(classe_note=None, annee_scolaire=None):
    """
    Fonction utilitaire pour synchroniser toutes les notes en masse.
    
    Peut être appelée manuellement ou via une commande de gestion.
    
    Args:
        classe_note: ClasseNote spécifique (optionnel)
        annee_scolaire: Année scolaire spécifique (optionnel, ex: "2025-2026")
    
    Returns:
        dict: Statistiques de synchronisation
    """
    from .models import ClasseNote, MatiereNote, Evaluation, NoteEleve, NoteMensuelle
    from django.db import transaction
    
    stats = {
        'classes_traitees': 0,
        'notes_creees': 0,
        'notes_mises_a_jour': 0,
        'notes_ignorees': 0,
        'erreurs': []
    }
    
    # Filtrer les classes
    classes_qs = ClasseNote.objects.filter(actif=True)
    if classe_note:
        classes_qs = classes_qs.filter(id=classe_note.id)
    if annee_scolaire:
        classes_qs = classes_qs.filter(annee_scolaire=annee_scolaire)
    
    periodes_mensuelles = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 
                           'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN']
    
    for cn in classes_qs:
        try:
            with transaction.atomic():
                matieres = MatiereNote.objects.filter(classe=cn, actif=True)
                
                for matiere in matieres:
                    evaluations = Evaluation.objects.filter(
                        matiere=matiere,
                        periode__in=periodes_mensuelles
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
                            
                            note_mens, created = NoteMensuelle.objects.update_or_create(
                                eleve=ne.eleve,
                                matiere=matiere,
                                mois=evaluation.periode,
                                annee_scolaire=cn.annee_scolaire,
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
                
                stats['classes_traitees'] += 1
                
        except Exception as e:
            stats['erreurs'].append(f"{cn.nom}: {str(e)}")
    
    # Vider le cache
    cache.clear()
    
    return stats
