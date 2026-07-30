"""
Module pour la génération des certificats d'appréciation
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import HttpResponse
from django.template.loader import render_to_string
from datetime import datetime
import base64
import os
import logging

from .models import ClasseNote, MatiereNote
from eleves.models import Eleve, Classe as ClasseEleve

logger = logging.getLogger(__name__)


@login_required
def certificats_appreciation_pdf(request):
    """
    Génère les certificats d'appréciation pour les 5 premiers élèves d'une classe
    """
    # Récupérer les paramètres
    classe_id = request.GET.get('classe_id')
    periode = request.GET.get('periode', '')
    
    if not classe_id:
        return HttpResponse("Classe non spécifiée", status=400)
    
    if not periode:
        return HttpResponse("Période non spécifiée", status=400)
    
    try:
        # Récupérer la classe
        classe_note = get_object_or_404(ClasseNote, pk=classe_id)
        
        # Récupérer l'école
        ecole = classe_note.ecole
        
        # Récupérer la classe élève correspondante
        classe_eleve = ClasseEleve.objects.filter(
            nom__iexact=classe_note.nom,
            annee_scolaire=classe_note.annee_scolaire,
            ecole=ecole
        ).first()
        
        if not classe_eleve:
            return HttpResponse(f"Classe élèves non trouvée pour {classe_note.nom}", status=404)
        
        # Récupérer les élèves actifs de la classe
        eleves = Eleve.objects.filter(classe=classe_eleve, statut='ACTIF')
        
        # Récupérer les matières de la classe
        matieres = MatiereNote.objects.filter(classe=classe_note, actif=True)
        
        # Détecter le niveau scolaire (maternelle, primaire, secondaire)
        from .calculs_moyennes import detecter_niveau_scolaire
        niveau_scolaire = detecter_niveau_scolaire(classe_note.nom)
        est_maternelle = (niveau_scolaire == 'MATERNELLE')
        est_primaire = (niveau_scolaire == 'PRIMAIRE')
        
        # Déterminer le type de système selon la période
        if periode in ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']:
            system_type = 'trimestriel'
        elif periode in ['SEMESTRE_1', 'SEMESTRE_2']:
            system_type = 'semestriel'
        elif periode in ['ANNUEL_TRIM']:
            system_type = 'annuel_trimestriel'
        elif periode in ['ANNUEL_SEM']:
            system_type = 'annuel_semestriel'
        else:
            system_type = 'mensuel'
        
        # UTILISER LA SOURCE CENTRALISÉE (calculer_rangs_classe_periode)
        # pour garantir que la moyenne sur le satisfécit corresponde exactement
        # à celle affichée sur le bulletin de l'élève.
        from .utils_rangs import calculer_rangs_classe_periode
        rangs_dict = calculer_rangs_classe_periode(classe_note, periode, use_cache=False)
        
        # Construire la liste des élèves avec rang et moyenne
        eleves_avec_rang = []
        for eleve in eleves:
            rang_info = rangs_dict.get(eleve.id)
            if rang_info and rang_info.get('rang_num', 999) <= 5:
                eleves_avec_rang.append({
                    'eleve': eleve,
                    'rang': rang_info.get('rang_num', 999),
                    'moyenne': float(rang_info['moyenne']),
                    'rang_num': rang_info.get('rang_num', 999)
                })
        
        # Trier par rang
        eleves_avec_rang.sort(key=lambda x: x['rang_num'])
        eleves_top5 = eleves_avec_rang[:5]
        
        if not eleves_top5:
            return HttpResponse("Aucun élève classé trouvé pour cette période", status=400)
        
        # Formater les rangs
        from .export_classement import formater_rang
        for eleve_data in eleves_top5:
            sexe = getattr(eleve_data['eleve'], 'sexe', 'M') or 'M'
            eleve_data['rang_formate'] = formater_rang(eleve_data['rang'], sexe)
        
        # Total élèves dans la classe
        total_eleves = Eleve.objects.filter(classe=classe_eleve, statut='ACTIF').count()
        
        # Encoder le logo en base64 si disponible
        logo_base64 = None
        if ecole and ecole.logo:
            try:
                logo_path = ecole.logo.path
                if os.path.exists(logo_path):
                    with open(logo_path, 'rb') as f:
                        logo_base64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception:
                pass
        
        # Libellé de la période
        periodes_labels = {
            'OCTOBRE': 'Mois d\'Octobre',
            'NOVEMBRE': 'Mois de Novembre',
            'DECEMBRE': 'Mois de Décembre',
            'JANVIER': 'Mois de Janvier',
            'FEVRIER': 'Mois de Février',
            'MARS': 'Mois de Mars',
            'AVRIL': 'Mois d\'Avril',
            'MAI': 'Mois de Mai',
            'JUIN': 'Mois de Juin',
            'TRIMESTRE_1': '1er Trimestre',
            'TRIMESTRE_2': '2ème Trimestre',
            'TRIMESTRE_3': '3ème Trimestre',
            'SEMESTRE_1': '1er Semestre',
            'SEMESTRE_2': '2ème Semestre',
            'ANNUEL_TRIM': 'Année Scolaire (Trimestres)',
            'ANNUEL_SEM': 'Année Scolaire (Semestres)',
        }
        periode_label = periodes_labels.get(periode, periode)
        
        # Contexte pour le template
        context = {
            'eleves_top5': eleves_top5,
            'classe': classe_note,
            'ecole': ecole,
            'logo_base64': logo_base64,
            'total_eleves': total_eleves,
            'periode': periode,
            'periode_label': periode_label,
            'annee_scolaire': classe_note.annee_scolaire,
            'date_emission': datetime.now().strftime('%d/%m/%Y'),
            'ville': getattr(ecole, 'adresse', 'Conakry').split(',')[0] if ecole else 'Conakry',
            'est_maternelle': est_maternelle,
            'est_primaire': est_primaire,
            'note_max': 10 if est_primaire else 20,
        }
        
        # Générer le HTML - utiliser un template différent pour la maternelle
        if est_maternelle:
            template_name = 'notes/certificat_maternelle.html'
        else:
            template_name = 'notes/certificat_appreciation.html'
        html_content = render_to_string(template_name, context, request=request)
        
        # Créer le PDF avec WeasyPrint (import lazy pour eviter l'erreur GTK au demarrage)
        from weasyprint import HTML, CSS
        base_url = request.build_absolute_uri('/')
        html = HTML(string=html_content, base_url=base_url)
        css = CSS(string='''
            @page {
                size: A4 landscape;
                margin: 10mm;
            }
        ''')

        try:
            pdf = html.write_pdf(stylesheets=[css])
        except Exception as wp_err:
            # Fallback : désactive le sous-ensemble des polices (évite les erreurs
            # "Unable to build parser" de fontTools sur certaines polices système)
            logger.warning(
                f"WeasyPrint erreur normale ({wp_err}), "
                "nouvelle tentative avec full_fonts=True"
            )
            html = HTML(string=html_content, base_url=base_url)
            pdf = html.write_pdf(stylesheets=[css], full_fonts=True)
        
        # Retourner le PDF
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="certificats_appreciation_{classe_note.nom}_{periode}.pdf"'
        return response
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Erreur lors de la génération des certificats: {str(e)}\n{tb}")
        return HttpResponse(f"Erreur: {str(e)}\n\n{tb}", status=500)
