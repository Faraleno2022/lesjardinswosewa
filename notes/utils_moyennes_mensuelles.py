"""
Utilitaires pour récupérer les moyennes mensuelles dynamiques
pour les bulletins trimestriels et semestriels
"""
from decimal import Decimal
from .models import NoteMensuelle, CompositionNote, Evaluation, NoteEleve
from .calculs_moyennes import calculer_moyenne_periode_guineenne, detecter_niveau_scolaire


def get_mois_periode(periode_type, periode, inclure_dernier_mois=True):
    """
    Retourne la liste des mois qui composent une période
    
    SYSTÈME SCOLAIRE GUINÉEN:
    - Année scolaire: Octobre → Juin
    - Le dernier mois de chaque période = Composition
    
    STRUCTURE DES TRIMESTRES:
    - Trimestre 1: Oct, Nov + Compo (Déc = Composition)
    - Trimestre 2: Jan, Fév + Compo (Mars = Composition)
    - Trimestre 3: Avr, Mai + Compo (Juin = Composition)
    
    STRUCTURE DES SEMESTRES:
    - Semestre 1: Oct, Nov, Déc, Jan + Compo (Fév = Composition)
    - Semestre 2: Mars, Avr, Mai + Compo (Juin = Composition)
    
    Args:
        periode_type: 'trimestre' ou 'semestre'
        periode: 'TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3', 'SEMESTRE_1', 'SEMESTRE_2'
        inclure_dernier_mois: Si False, exclut le dernier mois (qui est la composition)
    
    Returns:
        list: Liste des mois (ex: ['OCTOBRE', 'NOVEMBRE'] pour T1 sans dernier mois)
    """
    mois = []
    
    if periode_type == 'trimestre':
        if periode == 'TRIMESTRE_1':
            # Oct, Nov + Compo en Déc
            mois = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE']
        elif periode == 'TRIMESTRE_2':
            # Jan, Fév + Compo en Mars
            mois = ['JANVIER', 'FEVRIER', 'MARS']
        elif periode == 'TRIMESTRE_3':
            # Avr, Mai + Compo en Juin
            mois = ['AVRIL', 'MAI', 'JUIN']
    
    elif periode_type == 'semestre':
        if periode == 'SEMESTRE_1':
            # Oct, Nov, Déc, Jan + Compo en Fév
            mois = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER']
        elif periode == 'SEMESTRE_2':
            # Mars, Avr, Mai + Compo en Juin
            mois = ['MARS', 'AVRIL', 'MAI', 'JUIN']
    
    # Si on n'inclut pas le dernier mois (qui est la composition)
    if not inclure_dernier_mois and mois:
        return mois[:-1]
    
    return mois


def get_mois_pour_moyenne_continue(periode_type, periode):
    """
    Retourne les mois à utiliser pour calculer la moyenne continue
    (tous les mois SAUF le dernier qui est la composition)
    """
    return get_mois_periode(periode_type, periode, inclure_dernier_mois=False)


def get_libelle_mois(mois):
    """
    Retourne le libellé français du mois
    """
    libelles = {
        'OCTOBRE': 'Oct.',
        'NOVEMBRE': 'Nov.',
        'DECEMBRE': 'Déc.',
        'JANVIER': 'Jan.',
        'FEVRIER': 'Fév.',
        'MARS': 'Mars',
        'AVRIL': 'Avr.',
        'MAI': 'Mai',
        'JUIN': 'Juin',
        'JUILLET': 'Juil.',
    }
    return libelles.get(mois, mois)


def calculer_moyennes_mensuelles_matiere(eleve, matiere, periode_type, periode):
    """
    Calcule les moyennes mensuelles d'une matière pour une période donnée
    
    IMPORTANT: Le dernier mois de chaque période est la COMPOSITION, donc on ne l'inclut pas
    dans les moyennes mensuelles (il sera récupéré séparément via calculer_composition_periode)
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        periode_type: 'trimestre' ou 'semestre'
        periode: 'TRIMESTRE_1', 'TRIMESTRE_2', etc.
    
    Returns:
        dict: {
            'moyennes_mensuelles': [
                {'mois': 'OCTOBRE', 'libelle': 'Oct.', 'moyenne': 15.5, 'absent': False},
                {'mois': 'NOVEMBRE', 'libelle': 'Nov.', 'moyenne': None, 'absent': True},
                ...
            ],
            'moyenne_continue': 14.2,  # Moyenne des mois non absents (hors composition)
            'nb_mois_evalues': 2
        }
    """
    # Récupérer les mois SANS le dernier (qui est la composition)
    mois_periode = get_mois_pour_moyenne_continue(periode_type, periode)
    moyennes_mensuelles = []
    total_moyennes = Decimal('0')
    nb_mois_evalues = 0
    
    for mois in mois_periode:
        moyenne_mois = None
        absent = False
        
        # Méthode 1: Chercher dans NoteMensuelle (système direct)
        try:
            note_mensuelle = NoteMensuelle.objects.get(
                eleve=eleve,
                matiere=matiere,
                mois=mois,
                annee_scolaire=matiere.classe.annee_scolaire
            )
            if note_mensuelle.absent:
                absent = True
                moyenne_mois = None
            else:
                moyenne_mois = float(note_mensuelle.note)
                
        except NoteMensuelle.DoesNotExist:
            # Méthode 2: Calculer depuis les évaluations du mois
            evaluations_mois = Evaluation.objects.filter(
                matiere=matiere,
                periode=mois
            )
            
            if evaluations_mois.exists():
                total_notes = Decimal('0')
                count_notes = 0
                toutes_absentes = True
                
                for evaluation in evaluations_mois:
                    try:
                        note_obj = NoteEleve.objects.get(eleve=eleve, evaluation=evaluation)
                        if not note_obj.absent and note_obj.note is not None:
                            # Convertir sur 20 si nécessaire
                            note_sur_20 = (note_obj.note / evaluation.note_sur) * 20
                            total_notes += Decimal(str(note_sur_20))
                            count_notes += 1
                            toutes_absentes = False
                    except NoteEleve.DoesNotExist:
                        pass
                
                if count_notes > 0:
                    moyenne_mois = round(float(total_notes / count_notes), 2)
                elif toutes_absentes:
                    absent = True
        
        # Ajouter à la liste
        moyennes_mensuelles.append({
            'mois': mois,
            'libelle': get_libelle_mois(mois),
            'moyenne': moyenne_mois,
            'absent': absent
        })
        
        # Compter pour la moyenne continue
        if moyenne_mois is not None and not absent:
            total_moyennes += Decimal(str(moyenne_mois))
            nb_mois_evalues += 1
    
    # Calculer la moyenne continue
    moyenne_continue = None
    if nb_mois_evalues > 0:
        moyenne_continue = round(float(total_moyennes / nb_mois_evalues), 2)
    
    return {
        'moyennes_mensuelles': moyennes_mensuelles,
        'moyenne_continue': moyenne_continue,
        'nb_mois_evalues': nb_mois_evalues
    }


def calculer_composition_periode(eleve, matiere, periode_type, periode):
    """
    Calcule la note de composition pour une période
    
    IMPORTANT: La composition correspond au DERNIER MOIS de chaque période:
    - Trimestre 1: Décembre
    - Trimestre 2: Mars
    - Trimestre 3: Juin
    - Semestre 1: Février
    - Semestre 2: Juillet
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        periode_type: 'trimestre' ou 'semestre'
        periode: 'TRIMESTRE_1', 'TRIMESTRE_2', etc.
    
    Returns:
        dict: {
            'note_composition': 16.5,
            'absent_composition': False
        }
    """
    note_composition = None
    absent_composition = False
    
    # Déterminer le mois de composition (dernier mois de la période)
    mois_complets = get_mois_periode(periode_type, periode, inclure_dernier_mois=True)
    mois_composition = mois_complets[-1] if mois_complets else None
    
    # MÉTHODE 1: Chercher d'abord dans CompositionNote (notes importées)
    try:
        compo_importee = CompositionNote.objects.get(
            eleve=eleve,
            matiere=matiere,
            periode=periode,
            annee_scolaire=matiere.classe.annee_scolaire
        )
        if compo_importee.absent:
            absent_composition = True
        elif compo_importee.note is not None:
            note_composition = float(compo_importee.note)
            return {
                'note_composition': note_composition,
                'absent_composition': absent_composition
            }
    except CompositionNote.DoesNotExist:
        pass
    
    # MÉTHODE 2: Chercher dans NoteMensuelle du dernier mois (qui est la composition)
    if mois_composition:
        try:
            note_mensuelle = NoteMensuelle.objects.get(
                eleve=eleve,
                matiere=matiere,
                mois=mois_composition,
                annee_scolaire=matiere.classe.annee_scolaire
            )
            if note_mensuelle.absent:
                absent_composition = True
            elif note_mensuelle.note is not None:
                note_composition = float(note_mensuelle.note)
                return {
                    'note_composition': note_composition,
                    'absent_composition': absent_composition
                }
        except NoteMensuelle.DoesNotExist:
            pass
    
    # MÉTHODE 3: Chercher dans les évaluations de type COMPOSITION/EXAMEN
    evaluations_compo = Evaluation.objects.filter(
        matiere=matiere,
        periode=periode,
        type_evaluation__in=['COMPOSITION', 'EXAMEN']
    )
    
    total_compo = Decimal('0')
    count_compo = 0
    
    for evaluation in evaluations_compo:
        try:
            note_obj = NoteEleve.objects.get(eleve=eleve, evaluation=evaluation)
            if note_obj.absent:
                absent_composition = True
            elif note_obj.note is not None:
                # Convertir sur 20 si nécessaire
                note_sur_20 = (note_obj.note / evaluation.note_sur) * 20
                total_compo += Decimal(str(note_sur_20))
                count_compo += 1
        except NoteEleve.DoesNotExist:
            pass
    
    if count_compo > 0:
        note_composition = round(float(total_compo / count_compo), 2)
        return {
            'note_composition': note_composition,
            'absent_composition': absent_composition
        }
    
    # MÉTHODE 4: Chercher dans les évaluations du dernier mois
    if mois_composition:
        evaluations_mois = Evaluation.objects.filter(
            matiere=matiere,
            periode=mois_composition
        )
        
        total_notes = Decimal('0')
        count_notes = 0
        
        for evaluation in evaluations_mois:
            try:
                note_obj = NoteEleve.objects.get(eleve=eleve, evaluation=evaluation)
                if note_obj.absent:
                    absent_composition = True
                elif note_obj.note is not None:
                    note_sur_20 = (note_obj.note / evaluation.note_sur) * 20
                    total_notes += Decimal(str(note_sur_20))
                    count_notes += 1
            except NoteEleve.DoesNotExist:
                pass
        
        if count_notes > 0:
            note_composition = round(float(total_notes / count_notes), 2)
    
    return {
        'note_composition': note_composition,
        'absent_composition': absent_composition
    }


def calculer_bulletin_avec_details_mensuels(eleve, matiere, periode_type, periode):
    """
    Calcule toutes les données nécessaires pour afficher un bulletin avec détails mensuels
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        periode_type: 'trimestre' ou 'semestre'
        periode: 'TRIMESTRE_1', 'TRIMESTRE_2', etc.
    
    Returns:
        dict: Données complètes pour l'affichage
    """
    # Récupérer les moyennes mensuelles
    data_mensuelles = calculer_moyennes_mensuelles_matiere(eleve, matiere, periode_type, periode)
    
    # Récupérer la composition
    data_composition = calculer_composition_periode(eleve, matiere, periode_type, periode)
    
    # Calculer la moyenne finale selon la nouvelle formule
    moyenne_continue = data_mensuelles['moyenne_continue']
    note_composition = data_composition['note_composition']
    
    moyenne_finale = None
    if moyenne_continue is not None and note_composition is not None:
        # Formule guineenne centralisee selon le niveau.
        # PAS d'arrondi — garder la précision complète pour le calcul des points
        niveau = detecter_niveau_scolaire(matiere.classe.nom if hasattr(matiere.classe, 'nom') else '')
        moyenne_finale = calculer_moyenne_periode_guineenne(
            moyenne_continue,
            note_composition,
            'PRIMAIRE' if niveau == 'PRIMAIRE' else 'SECONDAIRE'
        )
    elif note_composition is not None:
        moyenne_finale = note_composition
    elif moyenne_continue is not None:
        moyenne_finale = moyenne_continue

    # Calculer les points (valeur EXACTE, arrondir à l'affichage seulement)
    points = None
    if moyenne_finale is not None:
        points = moyenne_finale * float(matiere.coefficient)
    
    return {
        'matiere': matiere,
        'moyennes_mensuelles': data_mensuelles['moyennes_mensuelles'],
        'moyenne_continue': moyenne_continue,
        'nb_mois_evalues': data_mensuelles['nb_mois_evalues'],
        'note_composition': note_composition,
        'absent_composition': data_composition['absent_composition'],
        'moyenne_finale': moyenne_finale,
        'coefficient': matiere.coefficient,
        'points': points,
        'periode_type': periode_type,
        'periode': periode
    }
