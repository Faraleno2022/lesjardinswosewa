"""
Module pour le téléchargement public de bulletins PDF via un lien sécurisé.
Permet aux parents de télécharger le bulletin sans se connecter au site.
"""

import hashlib
import hmac
from datetime import datetime, timedelta
from django.conf import settings
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging

from eleves.models import Eleve
from .models import ClasseNote

logger = logging.getLogger(__name__)

# Clé secrète pour signer les tokens (utiliser SECRET_KEY de Django)
def get_secret_key():
    return getattr(settings, 'SECRET_KEY', 'default-secret-key')


def generer_token_bulletin(eleve_id, classe_note_id, periode, duree_validite_jours=30):
    """
    Génère un token sécurisé pour accéder au bulletin sans authentification.
    
    Le token est valide pendant `duree_validite_jours` jours.
    Format: {timestamp}_{signature}
    """
    # Timestamp d'expiration
    expiration = datetime.now() + timedelta(days=duree_validite_jours)
    timestamp = int(expiration.timestamp())
    
    # Données à signer
    data = f"{eleve_id}:{classe_note_id}:{periode}:{timestamp}"
    
    # Signature HMAC
    signature = hmac.new(
        get_secret_key().encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()[:32]  # Prendre les 32 premiers caractères
    
    return f"{timestamp}_{signature}"


def verifier_token_bulletin(eleve_id, classe_note_id, periode, token):
    """
    Vérifie si le token est valide pour accéder au bulletin.
    
    Returns:
        bool: True si le token est valide, False sinon
    """
    try:
        parts = token.split('_')
        if len(parts) != 2:
            return False
        
        timestamp_str, signature_fournie = parts
        timestamp = int(timestamp_str)
        
        # Vérifier si le token n'a pas expiré
        if datetime.now().timestamp() > timestamp:
            logger.warning(f"Token expiré pour bulletin eleve={eleve_id}")
            return False
        
        # Recalculer la signature
        data = f"{eleve_id}:{classe_note_id}:{periode}:{timestamp}"
        signature_attendue = hmac.new(
            get_secret_key().encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()[:32]
        
        # Comparer les signatures de manière sécurisée
        return hmac.compare_digest(signature_fournie, signature_attendue)
        
    except Exception as e:
        logger.error(f"Erreur vérification token: {e}")
        return False


def generer_url_bulletin_public(request, eleve_id, classe_note_id, periode):
    """
    Génère l'URL publique complète pour télécharger le bulletin.
    """
    token = generer_token_bulletin(eleve_id, classe_note_id, periode)
    
    # Construire l'URL absolue
    base_url = request.build_absolute_uri('/')[:-1]  # Enlever le / final
    url = f"{base_url}/notes/bulletin-public/{eleve_id}/{classe_note_id}/{periode}/?token={token}"
    
    return url


def bulletin_public_pdf(request, eleve_id, classe_note_id, periode):
    """
    Vue publique pour télécharger le bulletin PDF sans authentification.
    Nécessite un token valide dans les paramètres GET.
    """
    # Récupérer le token
    token = request.GET.get('token', '')
    
    if not token:
        logger.warning(f"Tentative d'accès bulletin public sans token: eleve={eleve_id}")
        raise Http404("Lien invalide ou expiré. Veuillez demander un nouveau lien.")
    
    # Vérifier le token
    if not verifier_token_bulletin(eleve_id, classe_note_id, periode, token):
        logger.warning(f"Token invalide pour bulletin: eleve={eleve_id}, token={token[:20]}...")
        raise Http404("Lien invalide ou expiré. Veuillez demander un nouveau lien à l'école.")
    
    # Token valide - générer le PDF
    try:
        from .calculs_moyennes import detecter_niveau_scolaire
        from .bulletin_intelligent import (
            CalculateurBulletinIntelligent, 
            generer_pdf_avec_filigrane
        )
        
        eleve = get_object_or_404(Eleve, id=eleve_id)
        classe_note = get_object_or_404(ClasseNote, id=classe_note_id)
        
        # Détecter si c'est une classe maternelle
        niveau_detecte = detecter_niveau_scolaire(classe_note.nom)
        est_maternelle = (niveau_detecte == 'MATERNELLE')
        
        # Si maternelle, utiliser le bulletin maternelle v2
        if est_maternelle:
            return _generer_bulletin_maternelle_public(request, eleve, classe_note, periode)
        
        # Déterminer le système et le type de système pour l'affichage
        systeme = 'SEMESTRE' if 'SEMESTRE' in periode else 'TRIMESTRE'
        system_type = 'mensuel'
        
        if 'ANNUEL_TRIM' in periode:
            system_type = 'annuel_trimestriel'
            systeme = 'TRIMESTRE'
        elif 'ANNUEL_SEM' in periode:
            system_type = 'annuel_semestriel'
            systeme = 'SEMESTRE'
        elif 'TRIMESTRE' in periode:
            system_type = 'trimestriel'
        elif 'SEMESTRE' in periode:
            system_type = 'semestriel'
        
        # Calculer le bulletin
        calculateur = CalculateurBulletinIntelligent(eleve, classe_note, periode, systeme)
        bulletin_data = calculateur.generer_bulletin()
        
        # Ajouter le system_type et la période
        bulletin_data['system_type'] = system_type
        bulletin_data['periode'] = periode
        
        # Enrichir avec les données détaillées selon le type de système
        from notes.calculs_moyennes import calculer_bulletin_intelligent
        
        matieres_enrichies = []
        for mat_data in bulletin_data.get('matieres', []):
            mat_obj = mat_data.get('matiere')
            if mat_obj:
                try:
                    # Utiliser la fonction centralisée intelligente
                    result = calculer_bulletin_intelligent(eleve, mat_obj, periode, system_type)
                    mat_data['moyennes_mensuelles'] = result.get('moyennes_mensuelles', [])
                    mat_data['note_composition'] = result.get('note_composition')
                    mat_data['moyenne_continue'] = result.get('moyenne_continue')
                    mat_data['moyenne'] = result.get('moyenne')
                    mat_data['points'] = result.get('points')
                except:
                    pass
            matieres_enrichies.append(mat_data)
        
        bulletin_data['matieres'] = matieres_enrichies
        
        # ===== RECALCULER LA MOYENNE GÉNÉRALE ET LE RANG POUR BULLETINS ANNUELS =====
        # IMPORTANT: Utiliser UNE SEULE SOURCE pour garantir la cohérence moyenne/rang
        if system_type in ['annuel_trimestriel', 'annuel_semestriel']:
            from notes.calculs_moyennes import (
                calculer_classement_classe, 
                detecter_niveau_scolaire,
                obtenir_mention_intelligente
            )
            from notes.models import MatiereNote
            from notes.bulletin_intelligent import formater_rang_intelligent
            from eleves.models import Classe as ClasseEleve
            
            # Récupérer les matières de la classe
            matieres = MatiereNote.objects.filter(classe=classe_note)
            
            # Récupérer tous les élèves de la classe
            classe_eleve = ClasseEleve.objects.filter(
                nom=classe_note.nom,
                annee_scolaire=classe_note.annee_scolaire,
                ecole=classe_note.ecole
            ).first()
            
            if classe_eleve:
                from eleves.models import Eleve as EleveModel
                eleves_classe = list(EleveModel.objects.filter(classe=classe_eleve, statut='ACTIF'))
                total_eleves = len(eleves_classe)
                bulletin_data['total_eleves'] = total_eleves
                
                # CALCUL UNIQUE: Le classement calcule les moyennes ET les rangs avec la même source
                classement_result = calculer_classement_classe(eleves_classe, matieres, periode, system_type)
                rang_map = classement_result.get('rang_map', {})
                details_map = classement_result.get('details_par_eleve', {})
                
                # Récupérer les données de l'élève depuis le classement (MÊME SOURCE)
                if eleve.id in details_map:
                    details_eleve = details_map[eleve.id]
                    bulletin_data['moyenne_generale'] = details_eleve.get('moyenne_generale')
                    bulletin_data['total_points'] = details_eleve.get('total_points', 0)
                    bulletin_data['total_coefficients'] = details_eleve.get('total_coefficients', 0)
                
                # Récupérer le rang de l'élève (MÊME SOURCE que la moyenne)
                rang_brut = rang_map.get(eleve.id, '-')
                if rang_brut and rang_brut != '-':
                    sexe = getattr(eleve, 'sexe', 'M')
                    bulletin_data['rang'] = formater_rang_intelligent(rang_brut, sexe, total_eleves)
                else:
                    bulletin_data['rang'] = '-'
            
            # Calculer la mention basée sur la moyenne (cohérente)
            niveau = detecter_niveau_scolaire(classe_note.nom)
            if bulletin_data.get('moyenne_generale'):
                bulletin_data['mention'] = obtenir_mention_intelligente(bulletin_data['moyenne_generale'], niveau)
        
        # Chemin du logo
        ecole = eleve.classe.ecole if eleve.classe else None
        logo_path = None
        if ecole and hasattr(ecole, 'logo') and ecole.logo:
            logo_path = ecole.logo.path
        
        # Ajouter le matricule et la photo aux données du bulletin
        bulletin_data['matricule'] = eleve.matricule
        if hasattr(eleve, 'photo') and eleve.photo:
            try:
                bulletin_data['photo_path'] = eleve.photo.path
            except Exception:
                bulletin_data['photo_path'] = None
        else:
            bulletin_data['photo_path'] = None

        # Générer le PDF avec l'école
        pdf_buffer = generer_pdf_avec_filigrane(bulletin_data, logo_path, ecole)
        
        # Réponse HTTP
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        filename = f"bulletin_{eleve.nom}_{eleve.prenom}_{periode}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        logger.info(f"Bulletin téléchargé via lien public: eleve={eleve_id}, periode={periode}")
        
        return response
        
    except Exception as e:
        logger.error(f"Erreur génération bulletin public: {e}")
        raise Http404("Erreur lors de la génération du bulletin. Veuillez réessayer.")


def _generer_bulletin_maternelle_public(request, eleve, classe_note, periode):
    """
    Génère le bulletin maternelle v2 pour le téléchargement public.
    Utilise exactement la même logique que bulletin_maternelle_v2_pdf dans views.py.
    """
    import base64
    import os
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from .models import AppreciationMaternelle, BulletinMaternelle, MatiereNote
    from .utils_rangs import calculer_rangs_classe_periode
    from .utils_maternelle import lettre_vers_note as _lettre_vers_note, note_vers_lettre as _note_vers_lettre
    
    # Mapper la période au format trimestre
    trimestre = periode
    if 'TRIMESTRE_1' in periode:
        trimestre = 'TRIMESTRE_1'
    elif 'TRIMESTRE_2' in periode:
        trimestre = 'TRIMESTRE_2'
    elif 'TRIMESTRE_3' in periode:
        trimestre = 'TRIMESTRE_3'
    
    # Récupérer le bulletin
    bulletin = BulletinMaternelle.objects.filter(
        eleve=eleve, classe=classe_note, trimestre=trimestre,
        annee_scolaire=classe_note.annee_scolaire
    ).first()
    
    # Récupérer les matières et appréciations (identique à views.py)
    matieres = MatiereNote.objects.filter(classe=classe_note, actif=True).order_by('nom')
    appreciations = AppreciationMaternelle.objects.filter(
        eleve=eleve, matiere__in=matieres, trimestre=trimestre,
        annee_scolaire=classe_note.annee_scolaire
    ).select_related('matiere')
    
    if not appreciations.exists():
        appreciations = AppreciationMaternelle.objects.filter(
            eleve=eleve, matiere__in=matieres, trimestre=trimestre
        ).select_related('matiere')
    
    # Préparer les notes (identique à views.py)
    notes_data = []
    for app in appreciations:
        notes_data.append({
            'matiere': app.matiere,
            'lettre': app.appreciation,
            'mention': dict(AppreciationMaternelle.APPRECIATION_CHOICES).get(app.appreciation, ''),
            'note': _lettre_vers_note(app.appreciation),
            'absent': app.absent
        })
    
    # Calculer moyenne et rang
    rangs_dict = calculer_rangs_classe_periode(classe_note, trimestre, use_cache=True)
    rang_info = rangs_dict.get(eleve.id, {})
    moyenne_pourcentage = rang_info.get('moyenne')  # Pourcentage d'acquisition
    
    # Déterminer lettre et mention générales basées sur le pourcentage
    lettre_generale = None
    mention_generale = ''
    if moyenne_pourcentage:
        note_sur_10 = float(moyenne_pourcentage) / 10  # 87.5% -> 8.75
        lettre_generale = _note_vers_lettre(note_sur_10)
        mention_generale = dict(AppreciationMaternelle.APPRECIATION_CHOICES).get(lettre_generale, '') if lettre_generale else ''
    
    # Encoder logo et photo
    ecole = classe_note.ecole
    logo_base64 = ''
    if ecole and ecole.logo:
        try:
            if os.path.exists(ecole.logo.path):
                with open(ecole.logo.path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
        except:
            pass
    
    photo_base64 = ''
    if hasattr(eleve, 'photo') and eleve.photo:
        try:
            if os.path.exists(eleve.photo.path):
                with open(eleve.photo.path, 'rb') as f:
                    photo_base64 = base64.b64encode(f.read()).decode('utf-8')
        except:
            pass
    
    # Préparer le contexte (IDENTIQUE à bulletin_maternelle_v2_pdf)
    context = {
        'eleve': eleve,
        'classe': classe_note,
        'ecole': ecole,
        'evaluation': {
            'trimestre': trimestre, 
            'annee_scolaire': classe_note.annee_scolaire,
            'get_trimestre_display': dict(BulletinMaternelle.TRIMESTRE_CHOICES).get(trimestre, trimestre)
        },
        'notes': notes_data,  # Clé 'notes' comme dans views.py
        'moyenne_pourcentage': f"{float(moyenne_pourcentage):.1f}%" if moyenne_pourcentage else None,
        'lettre_generale': lettre_generale,
        'mention_generale': mention_generale,
        'rang': rang_info.get('rang', '-'),
        'total_eleves': rang_info.get('total_eleves'),
        'analyses_selectionnees': bulletin.get_analyses_display() if bulletin else [],
        'recommandations_selectionnees': bulletin.get_recommandations_display() if bulletin else [],
        'logo_base64': logo_base64,
        'photo_base64': photo_base64,
        'date_impression': timezone.now(),
    }
    
    # Générer le HTML avec le template maternelle v2
    html_content = render_to_string('notes/maternelle/bulletin_pdf.html', context)
    
    # Générer le PDF
    pdf_file = HTML(string=html_content).write_pdf()
    
    # Réponse HTTP
    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"bulletin_maternelle_{eleve.nom}_{eleve.prenom}_{periode}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    logger.info(f"Bulletin maternelle téléchargé via lien public: eleve={eleve.id}, periode={periode}")
    
    return response
