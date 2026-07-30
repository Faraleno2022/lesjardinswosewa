"""
Vues pour l'importation de notes depuis fichiers Excel/CSV
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from io import BytesIO

from .models import ClasseNote, MatiereNote, Evaluation
from utilisateurs.permissions import can_manage_notes
from eleves.utils_annee import get_annee_active


@login_required
@require_http_methods(["GET", "POST"])
def importer_notes(request):
    """
    Vue principale pour importer des notes
    """
    if not can_manage_notes(request.user):
        messages.error(request, "Vous n'avez pas la permission de gérer les notes.")
        return redirect('notes:consulter_notes')

    # Récupérer les classes (filtrées par année active)
    from utilisateurs.utils import user_school
    ecole = user_school(request.user) if not request.user.is_superuser else None
    annee_active = get_annee_active(request, ecole) if ecole else None

    if ecole and annee_active:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True, annee_scolaire=annee_active).order_by('nom')
    elif ecole:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True).order_by('nom')
    else:
        classes = ClasseNote.objects.filter(actif=True).order_by('nom')
    
    context = {
        'classes': classes,
        'periodes_mensuelles': [
            ('OCTOBRE', 'Octobre'),
            ('NOVEMBRE', 'Novembre'),
            ('DECEMBRE', 'Décembre'),
            ('JANVIER', 'Janvier'),
            ('FEVRIER', 'Février'),
            ('MARS', 'Mars'),
            ('AVRIL', 'Avril'),
            ('MAI', 'Mai'),
        ],
        'periodes_trimestrielles': [
            ('TRIMESTRE_1', 'Trimestre 1'),
            ('TRIMESTRE_2', 'Trimestre 2'),
            ('TRIMESTRE_3', 'Trimestre 3'),
        ],
        'periodes_semestrielles': [
            ('SEMESTRE_1', 'Semestre 1'),
            ('SEMESTRE_2', 'Semestre 2'),
        ],
        'types_import': [
            ('MENSUELLE', 'Notes Mensuelles'),
            ('COMPOSITION', 'Notes de Composition'),
            ('EVALUATION', 'Notes d\'Évaluation'),
        ]
    }
    
    if request.method == 'POST':
        return _traiter_import(request)
    
    return render(request, 'notes/importer_notes.html', context)


def _traiter_import(request):
    from .import_notes import (
        ImportNotesValidator,
        ImportNotesProcessor,
        ImportNotesError,
        lire_fichier_import,
    )

    """Traite l'importation du fichier"""
    # Récupérer les paramètres
    classe_id = request.POST.get('classe')
    matiere_id = request.POST.get('matiere')
    periode = request.POST.get('periode')
    annee_scolaire = request.POST.get('annee_scolaire')
    type_import = request.POST.get('type_import', 'MENSUELLE')
    evaluation_id = request.POST.get('evaluation')
    fichier = request.FILES.get('fichier')
    
    # Validation des paramètres
    if not all([classe_id, matiere_id, periode, annee_scolaire]):
        messages.error(request, "Tous les champs sont obligatoires.")
        return redirect('notes:importer_notes')
    
    if not fichier:
        messages.error(request, "Veuillez sélectionner un fichier.")
        return redirect('notes:importer_notes')
    
    if type_import == 'EVALUATION' and not evaluation_id:
        messages.error(request, "Veuillez sélectionner une évaluation.")
        return redirect('notes:importer_notes')
    
    try:
        # Lire le fichier
        df = lire_fichier_import(fichier)
        
        # Valider le fichier
        validator = ImportNotesValidator(
            df, 
            classe_id=classe_id,
            matiere_id=matiere_id,
            evaluation_id=evaluation_id,
            type_import=type_import
        )
        
        if not validator.valider():
            # Afficher les erreurs
            for erreur in validator.erreurs:
                messages.error(request, erreur)
            for avertissement in validator.avertissements:
                messages.warning(request, avertissement)
            return redirect('notes:importer_notes')
        
        # Afficher les avertissements
        for avertissement in validator.avertissements:
            messages.warning(request, avertissement)
        
        # Importer les notes
        processor = ImportNotesProcessor(
            df,
            classe_id=classe_id,
            matiere_id=matiere_id,
            periode=periode,
            annee_scolaire=annee_scolaire,
            type_import=type_import,
            evaluation_id=evaluation_id,
            user=request.user,
            colonnes_mapping=getattr(validator, 'colonnes_mapping', None)
        )
        
        stats = processor.importer()
        
        # Afficher le résultat
        messages.success(
            request,
            f"Importation réussie! "
            f"{stats['importees']} note(s) créée(s), "
            f"{stats['modifiees']} note(s) mise(s) à jour, "
            f"{stats['absents']} absent(s). "
            f"{stats['erreurs']} erreur(s)."
        )
        
        return redirect('notes:consulter_notes')
    
    except ImportNotesError as e:
        messages.error(request, f"Erreur d'importation: {e}")
        return redirect('notes:importer_notes')
    
    except Exception as e:
        messages.error(request, f"Erreur inattendue: {e}")
        return redirect('notes:importer_notes')


@login_required
def telecharger_template_import(request):
    import pandas as pd
    from .import_notes import generer_template_excel

    """
    Télécharge un fichier template Excel pour l'importation
    """
    classe_id = request.GET.get('classe')
    matiere_id = request.GET.get('matiere')
    type_import = request.GET.get('type_import', 'MENSUELLE')
    
    if not classe_id or not matiere_id:
        messages.error(request, "Veuillez sélectionner une classe et une matière.")
        return redirect('notes:importer_notes')
    
    try:
        # Générer le template
        df = generer_template_excel(classe_id, matiere_id, type_import)
        
        # Créer le fichier Excel en mémoire
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Notes')
            
            # Formater le fichier
            workbook = writer.book
            worksheet = writer.sheets['Notes']
            
            # Largeur des colonnes
            worksheet.column_dimensions['A'].width = 15  # Matricule
            worksheet.column_dimensions['B'].width = 15  # Prénom
            worksheet.column_dimensions['C'].width = 15  # Nom
            worksheet.column_dimensions['D'].width = 10  # Note
            worksheet.column_dimensions['E'].width = 10  # Absent
            
            # Style de l'en-tête
            from openpyxl.styles import Font, PatternFill, Alignment
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF")
            
            for cell in worksheet[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal='center', vertical='center')
        
        output.seek(0)
        
        # Récupérer les noms pour le fichier
        classe = ClasseNote.objects.get(id=classe_id)
        matiere = MatiereNote.objects.get(id=matiere_id)
        
        # Préparer la réponse
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        filename = f"template_notes_{classe.nom}_{matiere.code}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    except Exception as e:
        messages.error(request, f"Erreur lors de la génération du template: {e}")
        return redirect('notes:importer_notes')


@login_required
def get_matieres_classe(request):
    """
    API pour récupérer les matières d'une classe (AJAX)
    """
    classe_id = request.GET.get('classe_id')
    
    if not classe_id:
        return JsonResponse({'error': 'Classe ID manquant'}, status=400)
    
    try:
        matieres = MatiereNote.objects.filter(
            classe_id=classe_id,
            actif=True
        ).values('id', 'nom', 'code')
        
        return JsonResponse({'matieres': list(matieres)})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_evaluations_matiere(request):
    """
    API pour récupérer les évaluations d'une matière (AJAX)
    """
    matiere_id = request.GET.get('matiere_id')
    
    if not matiere_id:
        return JsonResponse({'error': 'Matière ID manquant'}, status=400)
    
    try:
        evaluations = Evaluation.objects.filter(
            matiere_id=matiere_id
        ).values('id', 'titre', 'type_evaluation', 'periode', 'date_evaluation')
        
        return JsonResponse({'evaluations': list(evaluations)})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ============================================================================
# IMPORTATION INTELLIGENTE - Template avec toutes les matières en colonnes
# ============================================================================

@login_required
def import_intelligent(request):
    """
    Vue principale pour l'importation intelligente de notes.
    Permet de télécharger un template et d'importer les notes.
    """
    from .import_intelligent import generer_template_intelligent, importer_notes_intelligent, ImportIntelligentError
    
    if not can_manage_notes(request.user):
        messages.error(request, "Vous n'avez pas la permission de gérer les notes.")
        return redirect('notes:consulter_notes')
    
    # Récupérer les classes (filtrées par année active)
    from utilisateurs.utils import user_school
    ecole = user_school(request.user) if not request.user.is_superuser else None
    annee_active = get_annee_active(request, ecole) if ecole else None

    if ecole and annee_active:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True, annee_scolaire=annee_active).order_by('nom')
    elif ecole:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True).order_by('nom')
    else:
        classes = ClasseNote.objects.filter(actif=True).order_by('nom')

    context = {
        'classes': classes,
        'periodes_mensuelles': [
            ('OCTOBRE', 'Octobre'),
            ('NOVEMBRE', 'Novembre'),
            ('DECEMBRE', 'Décembre'),
            ('JANVIER', 'Janvier'),
            ('FEVRIER', 'Février'),
            ('MARS', 'Mars'),
            ('AVRIL', 'Avril'),
            ('MAI', 'Mai'),
            ('JUIN', 'Juin'),
        ],
        'periodes_trimestrielles': [
            ('TRIMESTRE_1', '1er Trimestre'),
            ('TRIMESTRE_2', '2ème Trimestre'),
            ('TRIMESTRE_3', '3ème Trimestre'),
        ],
        'periodes_semestrielles': [
            ('SEMESTRE_1', '1er Semestre'),
            ('SEMESTRE_2', '2ème Semestre'),
        ],
    }
    
    if request.method == 'POST':
        # Traiter l'importation
        classe_id = request.POST.get('classe')
        periode = request.POST.get('periode')
        annee_scolaire = request.POST.get('annee_scolaire')
        type_notes = request.POST.get('type_notes', 'MENSUELLE')
        fichier = request.FILES.get('fichier')
        
        if not all([classe_id, periode, annee_scolaire]):
            messages.error(request, "Veuillez remplir tous les champs obligatoires.")
            return render(request, 'notes/import_intelligent.html', context)
        
        if not fichier:
            messages.error(request, "Veuillez sélectionner un fichier Excel.")
            return render(request, 'notes/import_intelligent.html', context)
        
        try:
            stats = importer_notes_intelligent(
                fichier=fichier,
                classe_id=classe_id,
                periode=periode,
                annee_scolaire=annee_scolaire,
                type_notes=type_notes,
                user=request.user
            )
            
            # Afficher les résultats
            messages.success(
                request,
                f"✅ Importation réussie! "
                f"{stats['importees']} note(s) créée(s), "
                f"{stats['modifiees']} mise(s) à jour. "
                f"Matières: {', '.join(stats['matieres_traitees'][:5])}{'...' if len(stats['matieres_traitees']) > 5 else ''}"
            )
            
            if stats['erreurs'] > 0:
                messages.warning(
                    request,
                    f"⚠️ {stats['erreurs']} erreur(s) rencontrée(s). "
                    f"Détails: {'; '.join(stats['erreurs_details'][:3])}"
                )
            
            return redirect('notes:consulter_notes')
        
        except ImportIntelligentError as e:
            messages.error(request, f"Erreur d'importation: {e}")
        except Exception as e:
            messages.error(request, f"Erreur inattendue: {e}")
    
    return render(request, 'notes/import_intelligent.html', context)


@login_required
def telecharger_template_intelligent(request):
    """
    Télécharge le template Excel intelligent avec toutes les matières en colonnes.
    """
    from .import_intelligent import generer_template_intelligent, ImportIntelligentError
    
    classe_id = request.GET.get('classe_id')
    periode = request.GET.get('periode', 'TRIMESTRE_1')
    
    if not classe_id:
        messages.error(request, "Veuillez sélectionner une classe.")
        return redirect('notes:import_intelligent')
    
    try:
        output, classe, matieres, note_max = generer_template_intelligent(classe_id, periode)
        
        # Préparer la réponse
        response = HttpResponse(
            output.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        # Nom du fichier
        nom_classe_clean = classe.nom.replace(' ', '_').replace('/', '-')
        filename = f"template_notes_{nom_classe_clean}_{periode}.xlsx"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
    
    except ImportIntelligentError as e:
        messages.error(request, f"Erreur: {e}")
        return redirect('notes:import_intelligent')
    except Exception as e:
        messages.error(request, f"Erreur inattendue: {e}")
        return redirect('notes:import_intelligent')


@login_required
def saisie_intelligente(request):
    """
    Vue pour la saisie intelligente des notes - toutes les matières en colonnes
    """
    from eleves.models import Eleve, Classe as ClasseEleve
    from .models import NoteMensuelle, CompositionNote
    from .calculs_moyennes import detecter_niveau_scolaire
    from utilisateurs.utils import user_school
    import json

    # Vérification des permissions
    if not can_manage_notes(request.user):
        messages.error(request, "Vous n'avez pas la permission de gérer les notes.")
        return redirect('notes:consulter_notes')

    ecole = user_school(request.user) if not request.user.is_superuser else None

    # Récupérer les classes (filtrées par année active et école)
    annee_active = get_annee_active(request, ecole) if ecole else None
    if ecole and annee_active:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True, annee_scolaire=annee_active).order_by('niveau', 'nom')
    elif ecole:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True).order_by('niveau', 'nom')
    else:
        classes = ClasseNote.objects.filter(actif=True).order_by('niveau', 'nom')

    # Paramètres de sélection — validation whitelist
    classe_id = request.GET.get('classe_id')
    VALID_TYPE_NOTES = {'mensuelle', 'composition'}
    VALID_PERIODES = {
        'OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER', 'MARS',
        'AVRIL', 'MAI', 'JUIN',
        'TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3',
        'SEMESTRE_1', 'SEMESTRE_2',
    }
    type_note = request.GET.get('type_note', '')
    if type_note and type_note not in VALID_TYPE_NOTES:
        type_note = ''
    periode = request.GET.get('periode', '')
    if periode and periode not in VALID_PERIODES:
        periode = ''

    classe_selectionnee = None
    matieres = []
    eleves = []
    notes_existantes = []
    note_max = 20
    
    # Périodes disponibles par défaut
    periodes_disponibles = []
    
    if classe_id:
        # Sécurité: vérifier que la classe appartient à l'école de l'utilisateur
        if ecole:
            classe_selectionnee = get_object_or_404(ClasseNote, pk=classe_id, ecole=ecole)
        else:
            classe_selectionnee = get_object_or_404(ClasseNote, pk=classe_id)
        matieres = list(MatiereNote.objects.filter(classe=classe_selectionnee, actif=True).order_by('nom'))
        
        # Détecter le niveau scolaire pour la note max
        niveau_detecte = detecter_niveau_scolaire(classe_selectionnee.nom)
        note_max = 10 if niveau_detecte == 'PRIMAIRE' else 20
        
        # Déterminer les périodes disponibles selon le type de note
        if type_note == 'mensuelle':
            periodes_disponibles = [
                ('OCTOBRE', 'Octobre'),
                ('NOVEMBRE', 'Novembre'),
                ('DECEMBRE', 'Décembre'),
                ('JANVIER', 'Janvier'),
                ('FEVRIER', 'Février'),
                ('MARS', 'Mars'),
                ('AVRIL', 'Avril'),
                ('MAI', 'Mai'),
                ('JUIN', 'Juin'),
            ]
        elif type_note == 'composition':
            periodes_disponibles = [
                ('TRIMESTRE_1', '1er Trimestre'),
                ('TRIMESTRE_2', '2ème Trimestre'),
                ('TRIMESTRE_3', '3ème Trimestre'),
                ('SEMESTRE_1', '1er Semestre'),
                ('SEMESTRE_2', '2ème Semestre'),
            ]
        
        # Récupérer les élèves
        classe_eleve = ClasseEleve.objects.filter(
            nom=classe_selectionnee.nom,
            annee_scolaire=classe_selectionnee.annee_scolaire,
            ecole=classe_selectionnee.ecole
        ).first()
        
        if not classe_eleve:
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe_selectionnee.nom,
                annee_scolaire=classe_selectionnee.annee_scolaire
            ).first()
        
        if classe_eleve:
            eleves = list(Eleve.objects.filter(classe=classe_eleve, statut='ACTIF').order_by('prenom', 'nom'))
        
        # Récupérer les notes existantes si période sélectionnée
        if periode and eleves and matieres:
            notes_list = []
            
            for eleve in eleves:
                for matiere in matieres:
                    if type_note == 'mensuelle':
                        note_obj = NoteMensuelle.objects.filter(
                            eleve=eleve,
                            matiere=matiere,
                            mois=periode,
                            annee_scolaire=classe_selectionnee.annee_scolaire
                        ).first()
                    else:
                        note_obj = CompositionNote.objects.filter(
                            eleve=eleve,
                            matiere=matiere,
                            periode=periode,
                            annee_scolaire=classe_selectionnee.annee_scolaire
                        ).first()
                    
                    if note_obj:
                        notes_list.append({
                            'eleve_id': str(eleve.id),
                            'matiere_id': str(matiere.id),
                            'note': float(note_obj.note) if note_obj.note is not None else None,
                            'absent': note_obj.absent if hasattr(note_obj, 'absent') else False
                        })
            
            notes_existantes = json.dumps(notes_list)
    
    # Labels pour l'affichage
    periode_display = dict([
        ('OCTOBRE', 'Octobre'), ('NOVEMBRE', 'Novembre'), ('DECEMBRE', 'Décembre'),
        ('JANVIER', 'Janvier'), ('FEVRIER', 'Février'), ('MARS', 'Mars'),
        ('AVRIL', 'Avril'), ('MAI', 'Mai'), ('JUIN', 'Juin'),
        ('TRIMESTRE_1', '1er Trimestre'), ('TRIMESTRE_2', '2ème Trimestre'),
        ('TRIMESTRE_3', '3ème Trimestre'), ('SEMESTRE_1', '1er Semestre'),
        ('SEMESTRE_2', '2ème Semestre'),
    ]).get(periode, periode)
    
    type_note_display = {'mensuelle': 'Note Mensuelle', 'composition': 'Composition'}.get(type_note, type_note)
    
    context = {
        'classes': classes,
        'classe_selectionnee': classe_selectionnee,
        'matieres': matieres,
        'eleves': eleves,
        'type_note': type_note,
        'periode': periode,
        'periodes_disponibles': periodes_disponibles,
        'note_max': note_max,
        'notes_existantes': notes_existantes,
        'periode_display': periode_display,
        'type_note_display': type_note_display,
    }
    
    return render(request, 'notes/saisie_intelligente.html', context)


@login_required
@require_http_methods(["POST"])
def saisie_intelligente_save(request):
    """
    API pour sauvegarder les notes de la saisie intelligente
    """
    from eleves.models import Eleve
    from .models import NoteMensuelle, CompositionNote
    from utilisateurs.utils import user_school
    from decimal import Decimal
    import json
    import logging

    # Vérification des permissions
    if not can_manage_notes(request.user):
        return JsonResponse({'success': False, 'error': 'Permission refusée'}, status=403)

    try:
        data = json.loads(request.body)
        type_note = data.get('type_note')
        periode = data.get('periode')
        notes = data.get('notes', [])

        # Validation whitelist des paramètres
        VALID_TYPE_NOTES = {'mensuelle', 'composition'}
        VALID_PERIODES = {
            'OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER', 'MARS',
            'AVRIL', 'MAI', 'JUIN',
            'TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3',
            'SEMESTRE_1', 'SEMESTRE_2',
        }

        if not type_note or type_note not in VALID_TYPE_NOTES:
            return JsonResponse({'success': False, 'error': 'Type de note invalide'})
        if not periode or periode not in VALID_PERIODES:
            return JsonResponse({'success': False, 'error': 'Période invalide'})

        # École de l'utilisateur (pour filtrage sécuritaire)
        ecole_user = user_school(request.user) if not request.user.is_superuser else None
        
        created_count = 0
        updated_count = 0
        absent_count = 0
        errors = []
        
        for note_data in notes:
            eleve_id = note_data.get('eleve_id')
            matiere_id = note_data.get('matiere_id')
            note_value = note_data.get('note')
            is_absent = note_data.get('absent', False)
            
            # Ignorer les entrées sans note et qui ne sont pas des absences
            if note_value is None and not is_absent:
                continue
            
            try:
                eleve = Eleve.objects.get(id=eleve_id)
                matiere = MatiereNote.objects.get(id=matiere_id)

                # Sécurité: vérifier que la matière appartient à l'école de l'utilisateur
                if ecole_user and matiere.classe.ecole != ecole_user:
                    errors.append(f"Matière {matiere_id} n'appartient pas à votre école")
                    continue

                annee_scolaire = matiere.classe.annee_scolaire
                
                # Déterminer la note max pour validation serveur
                from .calculs_moyennes import detecter_niveau_scolaire
                _note_max = 10 if detecter_niveau_scolaire(matiere.classe.nom) == 'PRIMAIRE' else 20

                # Pour les absents, stocker note=0 avec absent=True
                if is_absent:
                    note_decimal = Decimal('0')
                else:
                    note_decimal = Decimal(str(note_value))
                    if note_decimal < 0 or note_decimal > _note_max:
                        errors.append(f"Note {note_value} hors limites [0-{_note_max}]")
                        continue
                
                if type_note == 'mensuelle':
                    note_obj, created = NoteMensuelle.objects.update_or_create(
                        eleve=eleve,
                        matiere=matiere,
                        mois=periode,
                        annee_scolaire=annee_scolaire,
                        defaults={
                            'note': note_decimal,
                            'absent': is_absent,
                            'cree_par': request.user
                        }
                    )
                else:
                    note_obj, created = CompositionNote.objects.update_or_create(
                        eleve=eleve,
                        matiere=matiere,
                        periode=periode,
                        annee_scolaire=annee_scolaire,
                        defaults={
                            'note': note_decimal,
                            'absent': is_absent,
                            'cree_par': request.user
                        }
                    )
                
                if is_absent:
                    absent_count += 1
                elif created:
                    created_count += 1
                else:
                    updated_count += 1
                
            except (Eleve.DoesNotExist, MatiereNote.DoesNotExist):
                continue
            except Exception as e:
                errors.append(str(e))
        
        total_saved = created_count + updated_count + absent_count
        
        # Invalider le cache des rangs/classements pour que les bulletins soient à jour
        if total_saved > 0:
            try:
                from .utils_rangs import invalider_cache_rangs
                # Récupérer la classe depuis la première note pour invalider le cache
                first_note = notes[0] if notes else None
                if first_note:
                    matiere_obj = MatiereNote.objects.filter(id=first_note.get('matiere_id')).first()
                    if matiere_obj:
                        invalider_cache_rangs(matiere_obj.classe, periode)
            except Exception:
                pass
        
        return JsonResponse({
            'success': True,
            'saved': total_saved,
            'created': created_count,
            'updated': updated_count,
            'absents': absent_count,
            'errors': errors
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Données JSON invalides'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
