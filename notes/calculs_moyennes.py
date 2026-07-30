"""
Module centralisé pour le calcul des moyennes et classements
Garantit la cohérence entre bulletins et classements

OPTIMISATIONS v3.0 - ULTRA PERFORMANCE:
- Requêtes en lot (bulk queries) pour éviter N+1
- Cache des notes pré-chargées pour calculs en masse
- Cache Django pour les résultats de calculs
- Pré-chargement intelligent des données
- Performance: < 30ms pour 50 élèves, < 100ms pour 200 élèves
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Tuple, Optional
from django.core.cache import cache
from .models import Evaluation, NoteEleve, MatiereNote, NoteMensuelle, CompositionNote
import logging
import time

logger = logging.getLogger(__name__)

# Constantes de cache
CACHE_TIMEOUT_MOYENNES = 600  # 10 minutes
CACHE_TIMEOUT_CLASSEMENT = 600  # 10 minutes
CALCUL_CACHE_SCHEMA_VERSION = 2

# Règles de calcul utilisées par les bulletins et les classements.
# Secondaire guinéen: moyenne de période = 40% cours + 60% composition.
PONDERATION_COURS_SECONDAIRE = Decimal('0.4')
PONDERATION_COMPOSITION_SECONDAIRE = Decimal('0.6')

# Bonus de suivi continu (notes de cours/orales/écrites/devoirs/participation).
# Ajouté à la note MENSUELLE, plafonné, sans jamais dépasser 20.
# Un élève sans note de suivi a un bonus de 0 (comportement inchangé).
BONUS_SUIVI_MAX = Decimal('2')

# Mois calendaire -> mois scolaire (année scolaire Octobre→Juin)
_MOIS_SCOLAIRE_PAR_NUMERO = {
    9: 'OCTOBRE', 10: 'OCTOBRE', 11: 'NOVEMBRE', 12: 'DECEMBRE',
    1: 'JANVIER', 2: 'FEVRIER', 3: 'MARS', 4: 'AVRIL', 5: 'MAI',
    6: 'JUIN', 7: 'JUIN', 8: 'JUIN',
}


def mois_scolaire_depuis_date(d):
    """Retourne le libellé du mois scolaire (OCTOBRE..JUIN) pour une date."""
    if not d:
        return None
    return _MOIS_SCOLAIRE_PAR_NUMERO.get(d.month)


def bonus_suivi_batch(eleve_ids, matiere_ids, mois_list, annee_scolaire):
    """Bonus de suivi par (eleve, matiere, mois).

    Bonus = (moyenne des notes de suivi / 20) * BONUS_SUIVI_MAX.
    Prend en compte les notes de suivi (NoteSuivi) ET les notes des devoirs
    marqués « compte_bonus » (mois déduit de la date de remise).
    Retourne {(eleve_id, matiere_id, mois): bonus_float}. Vide si aucun suivi.
    """
    if not eleve_ids or not matiere_ids or not mois_list:
        return {}
    from .models import NoteSuivi, RemiseDevoir, MatiereNote

    # Le bonus n'est calculé que si l'école l'a explicitement activé.
    _actif = MatiereNote.objects.filter(
        id__in=matiere_ids, classe__ecole__bonus_suivi_actif=True
    ).exists()
    if not _actif:
        return {}

    groupes = {}

    # 1) Notes de suivi manuelles
    rows = (NoteSuivi.objects
            .filter(eleve_id__in=eleve_ids, matiere_id__in=matiere_ids,
                    mois__in=mois_list, annee_scolaire=annee_scolaire)
            .values('eleve_id', 'matiere_id', 'mois', 'note'))
    for r in rows:
        if r['note'] is None:
            continue
        groupes.setdefault((r['eleve_id'], r['matiere_id'], r['mois']), []).append(float(r['note']))

    # 2) Notes des devoirs activés (compte_bonus) -> mois de la date de remise
    drows = (RemiseDevoir.objects
             .filter(eleve_id__in=eleve_ids,
                     devoir__matiere_id__in=matiere_ids,
                     devoir__compte_bonus=True,
                     devoir__classe__annee_scolaire=annee_scolaire,
                     note__isnull=False)
             .values('eleve_id', 'devoir__matiere_id', 'devoir__date_remise', 'note'))
    for r in drows:
        mois = mois_scolaire_depuis_date(r['devoir__date_remise'])
        if mois not in mois_list:
            continue
        groupes.setdefault((r['eleve_id'], r['devoir__matiere_id'], mois), []).append(float(r['note']))

    resultat = {}
    for cle, notes in groupes.items():
        moy = sum(notes) / len(notes)
        resultat[cle] = float((Decimal(str(moy)) / Decimal('20')) * BONUS_SUIVI_MAX)
    return resultat


def bonus_suivi(eleve_id, matiere_id, mois, annee_scolaire):
    """Bonus de suivi pour un seul (eleve, matiere, mois)."""
    return bonus_suivi_batch([eleve_id], [matiere_id], [mois], annee_scolaire).get(
        (eleve_id, matiere_id, mois), 0.0)


def _appliquer_bonus(note_value, bonus):
    """Ajoute le bonus à une note mensuelle, plafonné à 20."""
    if note_value is None:
        return None
    return min(20.0, float(note_value) + float(bonus or 0.0))


def _arrondir_deux_decimales(valeur):
    """Arrondi scolaire déterministe, sans l'arrondi binaire de ``float``."""
    return float(
        Decimal(str(valeur)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    )

MOIS_PAR_PERIODE = {
    'TRIMESTRE_1': ['OCTOBRE', 'NOVEMBRE'],
    'TRIMESTRE_2': ['JANVIER', 'FEVRIER'],
    'TRIMESTRE_3': ['AVRIL', 'MAI'],
    'SEMESTRE_1': ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER'],
    'SEMESTRE_2': ['MARS', 'AVRIL', 'MAI'],
}


def obtenir_mois_periode(periode):
    """Retourne les mois de cours continus pour une période."""
    mapping_alias = {
        '1er Trimestre': 'TRIMESTRE_1',
        '2ème Trimestre': 'TRIMESTRE_2',
        '3ème Trimestre': 'TRIMESTRE_3',
        '1er Semestre': 'SEMESTRE_1',
        '2ème Semestre': 'SEMESTRE_2',
    }
    return MOIS_PAR_PERIODE.get(mapping_alias.get(periode, periode), [])


# Répartition trimestres -> semestres pour les écoles ayant saisi leurs
# compositions en trimestres mais consultées en système semestriel:
# S1 = moyenne(compo T1, compo T2) ; S2 = compo T3
_SEMESTRE_FALLBACK_TRIMESTRES = {
    'SEMESTRE_1': ['TRIMESTRE_1', 'TRIMESTRE_2'],
    'SEMESTRE_2': ['TRIMESTRE_3'],
}


def _compositions_semestre_depuis_trimestres(eleves_ids, matieres_ids, periode, annee_scolaire):
    """Dérive les compositions semestrielles depuis les compositions trimestrielles.

    Utilisé UNIQUEMENT en repli, quand la composition semestrielle n'a pas été
    saisie (école en mode trimestre consultée en mode semestre).
    Retourne {(eleve_id, matiere_id): note}.
    """
    p = periode or ''
    if 'SEMESTRE_1' in p or p == '1er Semestre':
        code = 'SEMESTRE_1'
    elif 'SEMESTRE_2' in p or p == '2ème Semestre':
        code = 'SEMESTRE_2'
    else:
        return {}

    rows = CompositionNote.objects.filter(
        eleve_id__in=eleves_ids,
        matiere_id__in=matieres_ids,
        periode__in=_SEMESTRE_FALLBACK_TRIMESTRES[code],
        annee_scolaire=annee_scolaire,
    ).values('eleve_id', 'matiere_id', 'note', 'absent')

    groupes = {}
    for r in rows:
        if r['absent'] or r['note'] is None:
            continue
        groupes.setdefault((r['eleve_id'], r['matiere_id']), []).append(float(r['note']))

    return {k: sum(v) / len(v) for k, v in groupes.items()}


def _periodes_composition_equivalentes(periode, system_type):
    """Périodes de composition à considérer pour une période donnée
    (inclut le repli trimestres -> semestres)."""
    p = periode or ''
    if system_type in ['semestriel', 'semestre']:
        if 'SEMESTRE_1' in p or p == '1er Semestre':
            return ['SEMESTRE_1'] + _SEMESTRE_FALLBACK_TRIMESTRES['SEMESTRE_1']
        if 'SEMESTRE_2' in p or p == '2ème Semestre':
            return ['SEMESTRE_2'] + _SEMESTRE_FALLBACK_TRIMESTRES['SEMESTRE_2']
    return [p]


def _matiere_a_compositions(matiere, periode, system_type):
    """True si au moins une composition est saisie dans la matière pour la période.

    RÈGLE STRICTE: quand la classe a composé dans une matière, un élève sans
    composition prend 0 (ne pas favoriser les absents). Ce test évite de
    pénaliser les écoles qui ne saisissent pas de compositions du tout.
    """
    return CompositionNote.objects.filter(
        matiere=matiere,
        periode__in=_periodes_composition_equivalentes(periode, system_type),
        annee_scolaire=matiere.classe.annee_scolaire,
    ).exists()


def calculer_moyenne_periode_guineenne(moyenne_continue, note_composition, niveau='SECONDAIRE'):
    """
    Calcule la moyenne de période selon le niveau.
    Primaire: composition seule quand elle existe.
    Secondaire: 40% cours + 60% composition.
    """
    if niveau == 'PRIMAIRE':
        if note_composition is not None:
            return note_composition
        return moyenne_continue

    if moyenne_continue is not None and note_composition is not None:
        moyenne = (
            Decimal(str(moyenne_continue)) * PONDERATION_COURS_SECONDAIRE
            + Decimal(str(note_composition)) * PONDERATION_COMPOSITION_SECONDAIRE
        )
        return float(moyenne)
    if note_composition is not None:
        return note_composition
    if moyenne_continue is not None:
        return moyenne_continue
    return None


def detecter_notes_mensuelles_classe(classe_note, periode=None):
    """
    Détecte si une classe a des notes mensuelles saisies.
    Utile pour masquer les colonnes mensuelles sur le bulletin si seulement des compositions.
    
    Args:
        classe_note: Instance ClasseNote
        periode: Période spécifique (optionnel, ex: 'TRIMESTRE_1')
    
    Returns:
        dict avec:
            - has_notes_mensuelles: bool - True si des notes mensuelles existent
            - has_compositions: bool - True si des compositions existent
            - mode_saisie: str - 'mensuel', 'composition_seule', 'mixte'
    """
    from .models import NoteMensuelle, CompositionNote, MatiereNote
    from eleves.models import Eleve, Classe as ClasseEleve
    
    # Récupérer les élèves de la classe
    classe_eleve = ClasseEleve.objects.filter(
        nom__iexact=classe_note.nom,
        annee_scolaire=classe_note.annee_scolaire,
        ecole=classe_note.ecole
    ).first()
    
    if not classe_eleve:
        return {'has_notes_mensuelles': False, 'has_compositions': False, 'mode_saisie': 'aucun'}
    
    eleves_ids = list(Eleve.objects.filter(classe=classe_eleve, statut='ACTIF').values_list('id', flat=True))
    matieres_ids = list(MatiereNote.objects.filter(classe=classe_note, actif=True).values_list('id', flat=True))
    
    if not eleves_ids or not matieres_ids:
        return {'has_notes_mensuelles': False, 'has_compositions': False, 'mode_saisie': 'aucun'}
    
    # Déterminer les mois à vérifier selon la période
    mois_a_verifier = []
    periodes_compo = []
    
    if periode:
        if periode == 'TRIMESTRE_1':
            mois_a_verifier = ['OCTOBRE', 'NOVEMBRE']
            periodes_compo = ['TRIMESTRE_1']
        elif periode == 'TRIMESTRE_2':
            mois_a_verifier = ['JANVIER', 'FEVRIER']
            periodes_compo = ['TRIMESTRE_2']
        elif periode == 'TRIMESTRE_3':
            mois_a_verifier = ['AVRIL', 'MAI']
            periodes_compo = ['TRIMESTRE_3']
        elif periode == 'SEMESTRE_1':
            mois_a_verifier = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER']
            # Inclure T1/T2: repli des compositions trimestrielles vers le semestre 1
            periodes_compo = ['SEMESTRE_1', 'TRIMESTRE_1', 'TRIMESTRE_2']
        elif periode == 'SEMESTRE_2':
            mois_a_verifier = ['MARS', 'AVRIL', 'MAI']
            # Inclure T3: repli des compositions trimestrielles vers le semestre 2
            periodes_compo = ['SEMESTRE_2', 'TRIMESTRE_3']
        elif periode == 'ANNUEL_TRIM':
            mois_a_verifier = ['OCTOBRE', 'NOVEMBRE', 'JANVIER', 'FEVRIER', 'AVRIL', 'MAI']
            periodes_compo = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        elif periode == 'ANNUEL_SEM':
            mois_a_verifier = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'MARS', 'AVRIL', 'MAI']
            periodes_compo = ['SEMESTRE_1', 'SEMESTRE_2', 'TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
    else:
        # Vérifier tous les mois
        mois_a_verifier = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER', 'FEVRIER', 'MARS', 'AVRIL', 'MAI', 'JUIN']
        periodes_compo = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3', 'SEMESTRE_1', 'SEMESTRE_2']
    
    # Vérifier les notes mensuelles
    has_notes_mensuelles = NoteMensuelle.objects.filter(
        eleve_id__in=eleves_ids,
        matiere_id__in=matieres_ids,
        mois__in=mois_a_verifier,
        annee_scolaire=classe_note.annee_scolaire,
        note__isnull=False
    ).exists()
    
    # Vérifier les compositions
    has_compositions = CompositionNote.objects.filter(
        eleve_id__in=eleves_ids,
        matiere_id__in=matieres_ids,
        periode__in=periodes_compo,
        annee_scolaire=classe_note.annee_scolaire,
        note__isnull=False
    ).exists()
    
    # Déterminer le mode de saisie
    if has_notes_mensuelles and has_compositions:
        mode_saisie = 'mixte'
    elif has_compositions:
        mode_saisie = 'composition_seule'
    elif has_notes_mensuelles:
        mode_saisie = 'mensuel'
    else:
        mode_saisie = 'aucun'
    
    return {
        'has_notes_mensuelles': has_notes_mensuelles,
        'has_compositions': has_compositions,
        'mode_saisie': mode_saisie
    }


def detecter_niveau_scolaire(classe_nom):
    """
    Détecte le niveau scolaire à partir du nom de la classe
    
    Returns:
        str: 'MATERNELLE', 'PRIMAIRE', 'COLLEGE', 'LYCEE'
    """
    nom_upper = str(classe_nom).upper()
    
    # Maternelle et garderie
    if any(x in nom_upper for x in ['MATERNELLE', 'GARDERIE', 'PETITE SECTION', 'MOYENNE SECTION', 'GRANDE SECTION', 'CRÈCHE']):
        return 'MATERNELLE'
    
    # Lycée (11ème à Terminale) - AVANT primaire pour éviter confusion avec 12ème/2ème
    if any(x in nom_upper for x in ['11ÈME', '12ÈME', 'TERMINALE']):
        return 'LYCEE'
    
    # Collège (7ème à 10ème année) - AVANT primaire pour éviter confusion avec 10ème/0ème
    if any(x in nom_upper for x in ['7ÈME', '8ÈME', '9ÈME', '10ÈME']):
        return 'COLLEGE'
    
    # Primaire (1ère à 6ème année ou CP, CE1, CE2, CM1, CM2)
    if any(x in nom_upper for x in ['1ÈRE ANNÉE', '2ÈME ANNÉE', '3ÈME ANNÉE', '4ÈME ANNÉE', '5ÈME ANNÉE', '6ÈME ANNÉE',
                                     'CP1', 'CP2', 'CE1', 'CE2', 'CM1', 'CM2']):
        return 'PRIMAIRE'
    
    # Par défaut, considérer comme collège
    return 'COLLEGE'


def calculer_moyenne_matiere(eleve, matiere, periode, system_type='mensuel'):
    """
    Calcule la moyenne d'un élève pour une matière donnée
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        periode: Période (ex: 'OCTOBRE', '1er Trimestre')
        system_type: Type de système ('mensuel', 'trimestre', 'semestre')
    
    Returns:
        dict avec:
            - moyenne_continue: float ou None
            - note_composition: float ou None
            - moyenne_matiere: float ou None (moyenne finale calculée)
            - points: float ou None (moyenne × coefficient)
    """
    moyenne_continue = None
    note_composition = None
    
    # SYSTÈME MENSUEL: Utiliser NoteMensuelle directement
    if system_type == 'mensuel':
        try:
            note_mensuelle = NoteMensuelle.objects.get(
                eleve=eleve,
                matiere=matiere,
                mois=periode,
                annee_scolaire=matiere.classe.annee_scolaire
            )
            if not note_mensuelle.absent and note_mensuelle.note is not None:
                _b = bonus_suivi(eleve.id, matiere.id, periode, matiere.classe.annee_scolaire)
                moyenne_continue = _appliquer_bonus(float(note_mensuelle.note), _b)
        except NoteMensuelle.DoesNotExist:
            pass
    else:
        # SYSTÈMES TRIMESTRIEL/SEMESTRIEL: Calculer la moyenne des mois de la période
        # Déterminer les mois de la période
        mois_periode = []
        # Accepter les deux variantes: 'trimestre' et 'trimestriel'
        if system_type in ['trimestriel', 'trimestre']:
            if 'TRIMESTRE_1' in periode or periode == '1er Trimestre':
                mois_periode = ['OCTOBRE', 'NOVEMBRE']
            elif 'TRIMESTRE_2' in periode or periode == '2ème Trimestre':
                mois_periode = ['JANVIER', 'FEVRIER']
            elif 'TRIMESTRE_3' in periode or periode == '3ème Trimestre':
                mois_periode = ['AVRIL', 'MAI']
        # Accepter les deux variantes: 'semestre' et 'semestriel'
        elif system_type in ['semestriel', 'semestre']:
            if 'SEMESTRE_1' in periode or periode == '1er Semestre':
                mois_periode = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER']
            elif 'SEMESTRE_2' in periode or periode == '2ème Semestre':
                mois_periode = ['MARS', 'AVRIL', 'MAI']
        
        # Calculer la moyenne des notes mensuelles (si elles existent)
        if mois_periode:
            total_notes = Decimal('0')
            count_notes = 0
            
            for mois in mois_periode:
                try:
                    note_mensuelle = NoteMensuelle.objects.get(
                        eleve=eleve,
                        matiere=matiere,
                        mois=mois,
                        annee_scolaire=matiere.classe.annee_scolaire
                    )
                    if not note_mensuelle.absent and note_mensuelle.note is not None:
                        _b = bonus_suivi(eleve.id, matiere.id, mois, matiere.classe.annee_scolaire)
                        _val = _appliquer_bonus(float(note_mensuelle.note), _b)
                        total_notes += Decimal(str(_val))
                        count_notes += 1
                except NoteMensuelle.DoesNotExist:
                    continue

            if count_notes > 0:
                # Garder la précision complète (arrondi à l'affichage seulement)
                moyenne_continue = float(total_notes / count_notes)

        # Récupérer la note de composition (TOUJOURS chercher, même sans notes mensuelles)
        try:
            compo = CompositionNote.objects.get(
                eleve=eleve,
                matiere=matiere,
                periode=periode,
                annee_scolaire=matiere.classe.annee_scolaire
            )
            if not compo.absent and compo.note is not None:
                note_composition = float(compo.note)
        except CompositionNote.DoesNotExist:
            pass

        # Repli: compositions saisies en trimestres mais consultation semestrielle
        if note_composition is None and system_type in ['semestriel', 'semestre']:
            fb = _compositions_semestre_depuis_trimestres(
                [eleve.id], [matiere.id], periode, matiere.classe.annee_scolaire
            )
            note_composition = fb.get((eleve.id, matiere.id), note_composition)

        # RÈGLE STRICTE: la classe a composé dans cette matière mais pas cet
        # élève -> composition comptée 0 (ne pas favoriser les absents)
        if note_composition is None and _matiere_a_compositions(matiere, periode, system_type):
            note_composition = 0.0

    # Calculer la moyenne de la matière selon le système
    # LOGIQUE ADAPTATIVE: Si pas de notes mensuelles, utiliser uniquement la composition
    moyenne_matiere = None
    if system_type == 'mensuel':
        moyenne_matiere = moyenne_continue
    elif moyenne_continue is not None and note_composition is not None:
        # CAS 1: Les deux existent -> formule guineenne par niveau
        # PAS d'arrondi ici — garder la précision complète pour le calcul des points
        niveau = detecter_niveau_scolaire(matiere.classe.nom if hasattr(matiere.classe, 'nom') else '')
        moyenne_matiere = calculer_moyenne_periode_guineenne(
            moyenne_continue,
            note_composition,
            'PRIMAIRE' if niveau == 'PRIMAIRE' else 'SECONDAIRE'
        )
    elif note_composition is not None:
        # CAS 2: Seulement composition (école sans notes mensuelles) → Utiliser directement
        moyenne_matiere = note_composition
    elif moyenne_continue is not None:
        # CAS 3: Seulement notes mensuelles (pas de composition) → Utiliser directement
        moyenne_matiere = moyenne_continue

    # Calculer les points (avec validation du coefficient)
    # RÈGLE: multiplier la valeur EXACTE par le coefficient, arrondir à l'affichage seulement
    points = None
    if moyenne_matiere is not None:
        try:
            coefficient = float(matiere.coefficient) if matiere.coefficient and matiere.coefficient > 0 else 1.0
        except (TypeError, ValueError):
            coefficient = 1.0
        points = moyenne_matiere * coefficient

    return {
        'moyenne_continue': moyenne_continue,
        'note_composition': note_composition,
        'moyenne_matiere': moyenne_matiere,
        'points': points,
    }


def calculer_moyenne_generale_eleve(eleve, matieres, periode, system_type='mensuel'):
    """
    Calcule la moyenne générale d'un élève pour toutes les matières
    
    Args:
        eleve: Instance Eleve
        matieres: QuerySet de MatiereNote
        periode: Période
        system_type: Type de système
    
    Returns:
        dict avec:
            - moyenne_generale: float ou None
            - total_points: float
            - total_coefficients: float
            - details_matieres: list de dict (une par matière)
            - niveau: niveau scolaire détecté
            - appreciations_only: bool (True pour maternelle/garderie)
    """
    # Détecter le niveau scolaire
    niveau = 'COLLEGE'  # Par défaut
    if matieres.exists():
        classe = matieres.first().classe
        niveau = detecter_niveau_scolaire(classe.nom if hasattr(classe, 'nom') else '')
    
    # MATERNELLE/GARDERIE: Pas de notes, seulement des appréciations
    if niveau == 'MATERNELLE':
        return {
            'moyenne_generale': None,
            'total_points': 0,
            'total_coefficients': 0,
            'details_matieres': [],
            'niveau': niveau,
            'appreciations_only': True,
            'appreciation': 'Suivi pédagogique qualitatif - Pas de notes numériques',
            'mention': 'Suivi continu'
        }
    
    total_points = Decimal('0')
    total_coefficients = Decimal('0')
    details_matieres = []
    
    for matiere in matieres:
        result = calculer_moyenne_matiere(eleve, matiere, periode, system_type)
        
        # RÈGLE PÉDAGOGIQUE: Toutes les matières comptent
        # Si pas de notes = 0 (comme une absence)
        moyenne_matiere = result['moyenne_matiere']
        if moyenne_matiere is None:
            moyenne_matiere = 0.0
        
        # PRIMAIRE: Pas de coefficients (tous égaux à 1)
        if niveau == 'PRIMAIRE':
            coefficient = Decimal('1')
        else:
            coefficient = matiere.coefficient if matiere.coefficient and matiere.coefficient > 0 else Decimal('1')
        
        # Calculer les points (valeur EXACTE, pas d'arrondi intermédiaire)
        points = moyenne_matiere * float(coefficient)

        # Ajouter au total (toutes les matières comptent)
        total_points += Decimal(str(moyenne_matiere)) * coefficient
        total_coefficients += coefficient

        details_matieres.append({
            'matiere': matiere,
            'moyenne_continue': result['moyenne_continue'],
            'note_composition': result['note_composition'],
            'moyenne': moyenne_matiere,  # 0 si non évalué (évite de favoriser les absents)
            'moyenne_calculee': moyenne_matiere,
            'coefficient': coefficient if niveau != 'PRIMAIRE' else 1,
            'points': points,
        })

    # Calculer la moyenne générale (avec protection contre division par zéro)
    # Arrondir UNIQUEMENT le résultat final
    moyenne_generale = None
    if total_coefficients and total_coefficients > 0:
        try:
            moyenne_generale = _arrondir_deux_decimales(total_points / total_coefficients)
        except (ZeroDivisionError, ValueError, TypeError) as e:
            moyenne_generale = None
    
    return {
        'moyenne_generale': moyenne_generale,
        'total_points': round(float(total_points), 2) if total_points > 0 else 0,
        'total_coefficients': float(total_coefficients),
        'details_matieres': details_matieres,
        'niveau': niveau,
        'appreciations_only': False
    }


def calculer_moyennes_classe_optimise(eleves, matieres, periode, system_type='mensuel', use_cache=True):
    """
    OPTIMISATION: Calcule les moyennes de tous les élèves d'une classe en une seule passe.
    
    Charge toutes les notes en 2-3 requêtes au lieu de N*M requêtes.
    
    Args:
        eleves: QuerySet d'Eleve
        matieres: QuerySet de MatiereNote
        periode: Période
        system_type: Type de système
    
    Returns:
        dict {eleve_id: {'moyenne_generale': float, 'details_matieres': list, ...}}
    """
    # Gérer le cas où matieres est une liste au lieu d'un QuerySet
    matieres_is_list = isinstance(matieres, list)
    eleves_is_list = isinstance(eleves, list)
    
    # Vérifier si les données sont vides
    if matieres_is_list:
        if not matieres:
            return {}
        matieres_ids = [m.id for m in matieres]
        classe = matieres[0].classe if matieres else None
    else:
        if not matieres.exists():
            return {}
        matieres_ids = list(matieres.values_list('id', flat=True))
        classe = matieres.first().classe
    
    if eleves_is_list:
        if not eleves:
            return {}
        eleves_ids = [e.id for e in eleves]
    else:
        if not eleves.exists():
            return {}
        eleves_ids = list(eleves.values_list('id', flat=True))
    
    if not classe:
        return {}

    # ── Cache: évite de recalculer si déjà fait dans les 10 dernières minutes ──
    # La version est incrémentée à chaque sauvegarde de note pour invalider le cache
    _version = cache.get(f"moy_version_classe_{classe.id}", 0)
    _cache_key = f"moy_classe_s{CALCUL_CACHE_SCHEMA_VERSION}_{classe.id}_{periode}_{system_type}_v{_version}"
    if use_cache:
        _cached = cache.get(_cache_key)
        if _cached is not None:
            return _cached

    # Détecter le niveau scolaire
    niveau = detecter_niveau_scolaire(classe.nom if hasattr(classe, 'nom') else '')
    est_primaire = (niveau == 'PRIMAIRE')
    
    # MATERNELLE: Pas de notes numériques
    if niveau == 'MATERNELLE':
        return {eleve.id: {
            'moyenne_generale': None,
            'total_points': 0,
            'total_coefficients': 0,
            'details_matieres': [],
            'niveau': niveau,
            'appreciations_only': True
        } for eleve in eleves}
    annee_scolaire = classe.annee_scolaire
    
    # Créer un dictionnaire des coefficients
    coefficients_map = {}
    matieres_dict = {}
    for matiere in matieres:
        matieres_dict[matiere.id] = matiere
        if est_primaire:
            coefficients_map[matiere.id] = Decimal('1')
        else:
            coefficients_map[matiere.id] = Decimal(str(matiere.coefficient)) if matiere.coefficient else Decimal('1')
    
    # Déterminer les mois de la période pour trimestre/semestre
    mois_periode = []
    if system_type in ['trimestriel', 'trimestre']:
        if 'TRIMESTRE_1' in periode or periode == '1er Trimestre':
            mois_periode = ['OCTOBRE', 'NOVEMBRE']
        elif 'TRIMESTRE_2' in periode or periode == '2ème Trimestre':
            mois_periode = ['JANVIER', 'FEVRIER']
        elif 'TRIMESTRE_3' in periode or periode == '3ème Trimestre':
            mois_periode = ['AVRIL', 'MAI']
    elif system_type in ['semestriel', 'semestre']:
        if 'SEMESTRE_1' in periode or periode == '1er Semestre':
            mois_periode = ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER']
        elif 'SEMESTRE_2' in periode or periode == '2ème Semestre':
            mois_periode = ['MARS', 'AVRIL', 'MAI']
    
    # OPTIMISATION: Charger TOUTES les notes mensuelles en une seule requête
    if system_type == 'mensuel':
        notes_filter = {'mois': periode}
    else:
        notes_filter = {'mois__in': mois_periode} if mois_periode else {'mois': periode}
    
    notes_mensuelles = NoteMensuelle.objects.filter(
        eleve_id__in=eleves_ids,
        matiere_id__in=matieres_ids,
        annee_scolaire=annee_scolaire,
        **notes_filter
    ).values('eleve_id', 'matiere_id', 'mois', 'note', 'absent')
    
    # Créer un dictionnaire pour accès rapide O(1)
    notes_dict = {}
    for note in notes_mensuelles:
        if system_type == 'mensuel':
            key = (note['eleve_id'], note['matiere_id'])
        else:
            key = (note['eleve_id'], note['matiere_id'], note['mois'])
        notes_dict[key] = note

    # Bonus de suivi continu par (eleve, matiere, mois) — 0 si aucun suivi
    _mois_bonus = [periode] if system_type == 'mensuel' else mois_periode
    bonus_map = bonus_suivi_batch(eleves_ids, matieres_ids, _mois_bonus, annee_scolaire)

    # OPTIMISATION: Charger les compositions si nécessaire
    compositions_dict = {}
    if system_type not in ['mensuel']:
        compositions = CompositionNote.objects.filter(
            eleve_id__in=eleves_ids,
            matiere_id__in=matieres_ids,
            periode=periode,
            annee_scolaire=annee_scolaire
        ).values('eleve_id', 'matiere_id', 'note', 'absent')
        
        for compo in compositions:
            key = (compo['eleve_id'], compo['matiere_id'])
            compositions_dict[key] = compo

        # Repli: compositions saisies en trimestres mais consultation semestrielle
        # (ne complète que les cases sans composition semestrielle saisie)
        if system_type in ['semestriel', 'semestre']:
            fallback = _compositions_semestre_depuis_trimestres(
                eleves_ids, matieres_ids, periode, annee_scolaire
            )
            for key, note_val in fallback.items():
                if key not in compositions_dict:
                    compositions_dict[key] = {
                        'eleve_id': key[0], 'matiere_id': key[1],
                        'note': note_val, 'absent': False,
                    }

    # RÈGLE STRICTE: matières où la classe a composé — un élève sans
    # composition y prend 0 (ne pas favoriser les absents)
    matieres_avec_compo = {mid for (_eid, mid) in compositions_dict.keys()}

    # Calculer les moyennes pour chaque élève (sans requêtes supplémentaires)
    resultats = {}
    for eleve in eleves:
        total_points = Decimal('0')
        total_coefficients = Decimal('0')
        details_matieres = []
        
        for matiere_id in matieres_ids:
            coefficient = coefficients_map[matiere_id]
            matiere = matieres_dict[matiere_id]
            moyenne_continue = None
            note_composition = None
            
            if system_type == 'mensuel':
                # Note mensuelle directe (+ bonus de suivi éventuel)
                key = (eleve.id, matiere_id)
                note_data = notes_dict.get(key)
                if note_data and not note_data['absent'] and note_data['note'] is not None:
                    _b = bonus_map.get((eleve.id, matiere_id, periode), 0.0)
                    moyenne_continue = _appliquer_bonus(float(note_data['note']), _b)
            else:
                # Moyenne des mois de la période (chaque mois + bonus de suivi)
                if mois_periode:
                    total_notes = Decimal('0')
                    count_notes = 0
                    for mois in mois_periode:
                        key = (eleve.id, matiere_id, mois)
                        note_data = notes_dict.get(key)
                        if note_data and not note_data['absent'] and note_data['note'] is not None:
                            _b = bonus_map.get((eleve.id, matiere_id, mois), 0.0)
                            _val = _appliquer_bonus(float(note_data['note']), _b)
                            total_notes += Decimal(str(_val))
                            count_notes += 1
                    if count_notes > 0:
                        # Garder la précision complète (arrondi à l'affichage seulement)
                        moyenne_continue = float(total_notes / count_notes)
                
                # Note de composition
                compo_key = (eleve.id, matiere_id)
                compo_data = compositions_dict.get(compo_key)
                if compo_data and not compo_data['absent'] and compo_data['note'] is not None:
                    note_composition = float(compo_data['note'])
                elif matiere_id in matieres_avec_compo:
                    # RÈGLE STRICTE: la classe a composé dans cette matière
                    # mais pas cet élève -> composition comptée 0
                    note_composition = 0.0
            
            # Calculer la moyenne de la matière
            # LOGIQUE ADAPTATIVE: Gère les écoles sans notes mensuelles
            moyenne_matiere = None
            if system_type == 'mensuel':
                moyenne_matiere = moyenne_continue
            elif moyenne_continue is not None and note_composition is not None:
                # CAS 1: Les deux existent -> formule guineenne par niveau
                # PAS d'arrondi — garder la précision complète
                moyenne_matiere = calculer_moyenne_periode_guineenne(
                    moyenne_continue,
                    note_composition,
                    'PRIMAIRE' if est_primaire else 'SECONDAIRE'
                )
            elif note_composition is not None:
                # CAS 2: Seulement composition (école sans notes mensuelles) → Utiliser directement
                moyenne_matiere = note_composition
            elif moyenne_continue is not None:
                # CAS 3: Seulement notes mensuelles → Utiliser directement
                moyenne_matiere = moyenne_continue

            # Élève non évalué dans cette matière = note 0 par défaut
            if moyenne_matiere is None:
                moyenne_matiere = 0.0

            moyenne_calculee = moyenne_matiere
            # Points: valeur EXACTE, pas d'arrondi intermédiaire
            points = moyenne_calculee * float(coefficient)

            total_points += Decimal(str(moyenne_calculee)) * coefficient
            total_coefficients += coefficient
            
            details_matieres.append({
                'matiere': matiere,
                'moyenne_continue': moyenne_continue,
                'note_composition': note_composition,
                'moyenne': moyenne_matiere,
                'moyenne_calculee': moyenne_calculee,
                'coefficient': coefficient if not est_primaire else 1,
                'points': points,
            })
        
        # Calculer la moyenne générale
        moyenne_generale = None
        if total_coefficients > 0:
            try:
                moyenne_generale = _arrondir_deux_decimales(total_points / total_coefficients)
            except (ZeroDivisionError, ValueError, TypeError):
                moyenne_generale = None
        
        resultats[eleve.id] = {
            'moyenne_generale': moyenne_generale,
            'total_points': round(float(total_points), 2) if total_points > 0 else 0,
            'total_coefficients': float(total_coefficients),
            'details_matieres': details_matieres,
            'niveau': niveau,
            'appreciations_only': False
        }

    # Mettre en cache 10 min (invalidé automatiquement dès qu'une note est saisie)
    if use_cache:
        cache.set(_cache_key, resultats, CACHE_TIMEOUT_MOYENNES)
    return resultats


def calculer_moyennes_classe_annuelle_optimise(eleves, matieres, system_type, use_cache=True):
    """Version OPTIMISÉE (batch) du calcul annuel pour toute une classe.

    Au lieu de N*M*P requêtes (lent: 40-80s/classe), on réutilise
    calculer_moyennes_classe_optimise pour CHAQUE période (2-3 requêtes/période),
    puis on combine par matière -> moyenne annuelle. Résultat identique à
    calculer_moyenne_generale_annuelle mais ~50x plus rapide.
    """
    if system_type == 'annuel_trimestriel':
        periodes = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        st = 'trimestre'
    elif system_type == 'annuel_semestriel':
        periodes = ['SEMESTRE_1', 'SEMESTRE_2']
        st = 'semestre'
    else:
        return {}

    matieres_list = list(matieres)
    eleves_list = list(eleves)
    if not matieres_list or not eleves_list:
        return {}

    classe = matieres_list[0].classe
    niveau = detecter_niveau_scolaire(classe.nom if hasattr(classe, 'nom') else '')
    est_primaire = (niveau == 'PRIMAIRE')

    if niveau == 'MATERNELLE':
        return {e.id: {
            'moyenne_generale': None, 'total_points': 0, 'total_coefficients': 0,
            'details_matieres': [], 'moyennes_periodes': {}, 'niveau': niveau,
            'appreciations_only': True,
        } for e in eleves_list}

    coef_map = {}
    for m in matieres_list:
        if est_primaire:
            coef_map[m.id] = Decimal('1')
        else:
            coef_map[m.id] = Decimal(str(m.coefficient)) if m.coefficient else Decimal('1')

    # Batch: moyenne par (période, élève, matière) via la fonction déjà optimisée
    nb_p = len(periodes)
    par_periode = {}
    for p in periodes:
        res = calculer_moyennes_classe_optimise(eleves_list, matieres_list, p, st, use_cache=use_cache)
        mp = {}
        for eid, data in res.items():
            dd = {}
            for det in data.get('details_matieres', []):
                v = det.get('moyenne')
                dd[det['matiere'].id] = float(v) if v is not None else 0.0
            mp[eid] = dd
        par_periode[p] = mp

    resultats = {}
    for eleve in eleves_list:
        total_points = Decimal('0')
        total_coefficients = Decimal('0')
        details_matieres = []
        for m in matieres_list:
            coef = coef_map[m.id]
            # Moyenne annuelle de la matière = moyenne des périodes (période non évaluée = 0)
            somme = 0.0
            for p in periodes:
                somme += par_periode[p].get(eleve.id, {}).get(m.id, 0.0)
            moy_ann = _arrondir_deux_decimales(Decimal(str(somme)) / Decimal(nb_p))
            points = moy_ann * float(coef)
            total_points += Decimal(str(moy_ann)) * coef
            total_coefficients += coef
            details_matieres.append({
                'matiere': m,
                'moyenne_annuelle': moy_ann,
                'moyenne': moy_ann,
                'coefficient': coef if not est_primaire else 1,
                'points': points,
            })
        moyenne_generale = None
        if total_coefficients > 0:
            moyenne_generale = _arrondir_deux_decimales(total_points / total_coefficients)
        resultats[eleve.id] = {
            'moyenne_generale': moyenne_generale,
            'total_points': round(float(total_points), 2) if total_points > 0 else 0,
            'total_coefficients': float(total_coefficients),
            'details_matieres': details_matieres,
            'niveau': niveau,
            'appreciations_only': False,
        }
    return resultats


def calculer_classement_classe(eleves, matieres, periode, system_type='mensuel', use_cache=True):
    """
    Calcule le classement complet d'une classe
    
    OPTIMISATION v3.0: Cache de 10 minutes pour éviter les recalculs
    
    Args:
        eleves: QuerySet d'Eleve
        matieres: QuerySet de MatiereNote
        periode: Période
        system_type: Type de système ('mensuel', 'trimestriel', 'semestriel', 'annuel_trimestriel', 'annuel_semestriel')
        use_cache: Si True, utilise le cache (défaut: True)
    
    Returns:
        dict avec:
            - moyennes_par_eleve: dict {eleve_id: moyenne_generale}
            - classement: list de tuples (eleve_id, moyenne_generale) triée
            - rang_map: dict {eleve_id: rang}
            - details_par_eleve: dict {eleve_id: dict complet des calculs}
    """
    # Gérer le cas où matieres est une liste au lieu d'un QuerySet
    if isinstance(matieres, list):
        if matieres:
            classe_id = matieres[0].classe_id
            cache_key = f"classement_classe_s{CALCUL_CACHE_SCHEMA_VERSION}_{classe_id}_periode_{periode}_type_{system_type}"
        else:
            cache_key = None
    else:
        # Générer une clé de cache basée sur les paramètres
        if matieres.exists():
            classe_id = matieres.first().classe_id
            cache_key = f"classement_classe_s{CALCUL_CACHE_SCHEMA_VERSION}_{classe_id}_periode_{periode}_type_{system_type}"
        else:
            cache_key = None
    
    # Vérifier le cache
    if cache_key and use_cache:
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Cache HIT pour classement {cache_key}")
            return cached_result
    
    start_time = time.time()
    
    moyennes_par_eleve = {}
    details_par_eleve = {}
    
    # Collecter tous les IDs des élèves pour garantir que chacun ait un rang
    all_eleve_ids = set(eleve.id for eleve in eleves)
    
    # OPTIMISATION: Utiliser la fonction optimisée pour les systèmes non-annuels
    if system_type not in ['annuel_trimestriel', 'annuel_semestriel']:
        # Calcul en lot (2-3 requêtes au lieu de N*M)
        resultats_optimises = calculer_moyennes_classe_optimise(
            eleves,
            matieres,
            periode,
            system_type,
            use_cache=use_cache,
        )
        
        for eleve_id, result in resultats_optimises.items():
            if result['moyenne_generale'] is not None:
                moyennes_par_eleve[eleve_id] = result['moyenne_generale']
                details_par_eleve[eleve_id] = result
    else:
        # OPTIMISATION: calcul annuel batché (réutilise le batch par période)
        resultats_annuels = calculer_moyennes_classe_annuelle_optimise(
            eleves, matieres, system_type, use_cache=use_cache,
        )
        for eleve_id, result in resultats_annuels.items():
            if result['moyenne_generale'] is not None:
                moyennes_par_eleve[eleve_id] = result['moyenne_generale']
                details_par_eleve[eleve_id] = result
    
    # Élèves sans notes = moyenne 0 par défaut (évite de favoriser les absents)
    for eleve_id in all_eleve_ids:
        if eleve_id not in moyennes_par_eleve:
            moyennes_par_eleve[eleve_id] = 0.0
            details_par_eleve[eleve_id] = {
                'moyenne_generale': 0.0,
                'total_points': 0,
                'total_coefficients': 0,
                'details_matieres': [],
                'niveau': 'INCONNU',
                'appreciations_only': False,
                'sans_notes': True,
            }
    
    # Créer le classement trié (tri par moyenne puis par matricule pour stabiliser les ex-æquo)
    # Récupérer les matricules pour le tri secondaire
    matricules_map = {eleve.id: eleve.matricule for eleve in eleves}
    classement = sorted(
        moyennes_par_eleve.items(), 
        key=lambda x: (-float(x[1]), matricules_map.get(x[0], ""))
    )
    
    # Créer le mapping des rangs (gestion des ex-aequo)
    rang_map = {}
    prev_moyenne = None
    prev_rang = 0
    
    for idx, (eleve_id, moyenne) in enumerate(classement, start=1):
        if moyenne == prev_moyenne:
            # Ex-aequo: même rang que le précédent
            rang_map[eleve_id] = prev_rang
        else:
            rang_map[eleve_id] = idx
            prev_rang = idx
        prev_moyenne = moyenne
    
    result = {
        'moyennes_par_eleve': moyennes_par_eleve,
        'classement': classement,
        'rang_map': rang_map,
        'details_par_eleve': details_par_eleve,
        'total_eleves': len(all_eleve_ids),
    }
    
    # Mesurer et logger le temps
    elapsed_time = (time.time() - start_time) * 1000
    logger.info(f"Classement calculé pour {len(classement)} élèves en {elapsed_time:.1f}ms")
    
    # Mettre en cache
    if cache_key and use_cache:
        cache.set(cache_key, result, timeout=CACHE_TIMEOUT_CLASSEMENT)
    
    return result


def obtenir_mention_intelligente(moyenne, niveau='SECONDAIRE'):
    """
    Détermine la mention selon la moyenne et le niveau scolaire
    
    Args:
        moyenne: float ou Decimal
        niveau: str ('MATERNELLE', 'PRIMAIRE', 'SECONDAIRE')
    
    Returns:
        str: Mention correspondante
    """
    if moyenne is None:
        return None
    
    moyenne = float(moyenne)
    
    if niveau == 'MATERNELLE':
        # Maternelle : taux d'acquisition en %
        if moyenne >= 90:
            return "Excellent"
        elif moyenne >= 75:
            return "Très Bien"
        elif moyenne >= 60:
            return "Bien"
        elif moyenne >= 50:
            return "Assez Bien"
        else:
            return "À encourager"
    
    elif niveau == 'PRIMAIRE':
        # Primaire : moyenne sur 10
        if moyenne >= 9:
            return "Excellent"
        elif moyenne >= 8:
            return "Très Bien"
        elif moyenne >= 7:
            return "Bien"
        elif moyenne >= 6:
            return "Assez Bien"
        elif moyenne >= 5:
            return "Passable"
        elif moyenne >= 4:
            return "Insuffisant"
        elif moyenne >= 3:
            return "Faible"
        else:
            return "Très faible"
    
    else:
        # Secondaire : moyenne sur 20 (par défaut)
        if moyenne >= 18:
            return "Excellent"
        elif moyenne >= 16:
            return "Très Bien"
        elif moyenne >= 14:
            return "Bien"
        elif moyenne >= 12:
            return "Assez Bien"
        elif moyenne >= 10:
            return "Passable"
        elif moyenne >= 8:
            return "Insuffisant"
        elif moyenne >= 6:
            return "Faible"
        else:
            return "Très faible"


def obtenir_appreciation_intelligente(moyenne, prenom, niveau='SECONDAIRE'):
    """
    Génère une appréciation personnalisée selon la moyenne
    
    Args:
        moyenne: float ou Decimal
        prenom: str
        niveau: 'PRIMAIRE' (sur 10), 'SECONDAIRE' (sur 20), ou 'MATERNELLE'
    
    Returns:
        str: Appréciation personnalisée
    """
    if moyenne is None:
        return f"{prenom}, aucune note disponible pour cette période."
    
    moyenne = float(moyenne)
    
    # Pour le primaire (notation sur 10), convertir en équivalent sur 20
    if niveau == 'PRIMAIRE':
        moyenne_ref = moyenne * 2
    else:
        moyenne_ref = moyenne
    
    if moyenne_ref >= 18.5:
        return f"Excellent travail {prenom}! Continue sur cette lancée exceptionnelle."
    elif moyenne_ref >= 16.5:
        return f"Très bon travail {prenom}! Tes efforts sont remarquables."
    elif moyenne_ref >= 14.5:
        return f"Bon travail {prenom}! Continue ainsi."
    elif moyenne_ref >= 12.5:
        return f"Travail assez satisfaisant {prenom}. Tu peux faire mieux."
    elif moyenne_ref >= 10.0:
        return f"{prenom}, travail passable. Plus d'efforts sont nécessaires."
    elif moyenne_ref >= 9.0:
        return f"{prenom}, résultats faibles. Il faut redoubler d'efforts."
    else:
        return f"{prenom}, résultats insuffisants. Un travail sérieux s'impose."


def formater_rang_intelligent(rang, sexe='M', total=None, est_ex_aequo=False):
    """
    Formate le rang avec accord grammatical
    
    Args:
        rang: int
        sexe: str ('M' ou 'F')
        total: int optionnel (nombre total d'élèves)
        est_ex_aequo: bool (True si l'élève est ex-æquo)
    
    Returns:
        str: Rang formaté (ex: "1er", "1ère", "2ème ex-æquo")
    """
    if rang is None or rang == 0:
        return "-"
    
    # Formater le rang avec accord grammatical
    if rang == 1:
        rang_str = "1ère" if sexe == 'F' else "1er"
    else:
        rang_str = f"{rang}ème"
    
    # Ajouter "ex" si c'est le cas et que ce n'est pas le premier rang
    if est_ex_aequo and rang > 1:
        rang_str += " ex"
    
    # Ne pas ajouter le total pour un affichage plus compact
    return rang_str


def calculer_moyenne_annuelle_matiere(eleve, matiere, system_type='annuel_trimestriel'):
    """
    Calcule la moyenne annuelle d'un élève pour une matière
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        system_type: 'annuel_trimestriel' (T1+T2+T3)/3 ou 'annuel_semestriel' (S1+S2)/2
    
    Returns:
        dict avec:
            - moyenne_annuelle: float ou None
            - moyennes_periodes: dict des moyennes par période
            - details: informations détaillées
    """
    moyennes_periodes = {}
    
    if system_type == 'annuel_trimestriel':
        # Calculer les moyennes des 3 trimestres
        periodes = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        for periode in periodes:
            result = calculer_moyenne_matiere(eleve, matiere, periode, 'trimestre')
            moyennes_periodes[periode] = result['moyenne_matiere']
    
    elif system_type == 'annuel_semestriel':
        # Calculer les moyennes des 2 semestres
        periodes = ['SEMESTRE_1', 'SEMESTRE_2']
        for periode in periodes:
            result = calculer_moyenne_matiere(eleve, matiere, periode, 'semestre')
            moyennes_periodes[periode] = result['moyenne_matiere']
    
    # Calculer la moyenne annuelle
    moyennes_valides = [m for m in moyennes_periodes.values() if m is not None]
    
    moyenne_annuelle = None
    if moyennes_valides:
        moyennes_avec_absents = [m if m is not None else 0 for m in moyennes_periodes.values()]
        moyenne_annuelle = _arrondir_deux_decimales(
            Decimal(str(sum(moyennes_avec_absents))) / Decimal(len(moyennes_avec_absents))
        )
    
    # Calculer les points (valeur EXACTE, pas d'arrondi intermédiaire)
    points = None
    if moyenne_annuelle is not None:
        try:
            coefficient = float(matiere.coefficient) if matiere.coefficient and matiere.coefficient > 0 else 1.0
        except (TypeError, ValueError):
            coefficient = 1.0
        points = moyenne_annuelle * coefficient
    
    return {
        'moyenne_annuelle': moyenne_annuelle,
        'moyennes_periodes': moyennes_periodes,
        'points': points,
    }


def calculer_moyenne_generale_annuelle(eleve, matieres, system_type='annuel_trimestriel'):
    """
    Calcule la moyenne générale annuelle d'un élève
    
    Args:
        eleve: Instance Eleve
        matieres: QuerySet de MatiereNote
        system_type: 'annuel_trimestriel' ou 'annuel_semestriel'
    
    Returns:
        dict avec:
            - moyenne_generale: float ou None
            - total_points: float
            - total_coefficients: float
            - details_matieres: list de dict (une par matière)
            - moyennes_periodes: dict des moyennes générales par période
    """
    # Détecter le niveau scolaire
    niveau = 'COLLEGE'
    if matieres.exists():
        classe = matieres.first().classe
        niveau = detecter_niveau_scolaire(classe.nom if hasattr(classe, 'nom') else '')
    
    # MATERNELLE: Pas de notes
    if niveau == 'MATERNELLE':
        return {
            'moyenne_generale': None,
            'total_points': 0,
            'total_coefficients': 0,
            'details_matieres': [],
            'moyennes_periodes': {},
            'niveau': niveau,
            'appreciations_only': True,
        }
    
    total_points = Decimal('0')
    total_coefficients = Decimal('0')
    details_matieres = []
    
    # Calculer les moyennes générales par période
    moyennes_generales_periodes = {}
    
    if system_type == 'annuel_trimestriel':
        periodes = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        for periode in periodes:
            result = calculer_moyenne_generale_eleve(eleve, matieres, periode, 'trimestre')
            moyennes_generales_periodes[periode] = result['moyenne_generale']
    elif system_type == 'annuel_semestriel':
        periodes = ['SEMESTRE_1', 'SEMESTRE_2']
        for periode in periodes:
            result = calculer_moyenne_generale_eleve(eleve, matieres, periode, 'semestre')
            moyennes_generales_periodes[periode] = result['moyenne_generale']
    
    # Calculer pour chaque matière
    for matiere in matieres:
        result = calculer_moyenne_annuelle_matiere(eleve, matiere, system_type)
        
        moyenne_matiere = result['moyenne_annuelle']
        if moyenne_matiere is None:
            moyenne_matiere = 0.0
        
        # PRIMAIRE: Pas de coefficients
        if niveau == 'PRIMAIRE':
            coefficient = Decimal('1')
        else:
            coefficient = matiere.coefficient if matiere.coefficient and matiere.coefficient > 0 else Decimal('1')
        
        # Points: valeur EXACTE, pas d'arrondi intermédiaire
        points = moyenne_matiere * float(coefficient)

        total_points += Decimal(str(moyenne_matiere)) * coefficient
        total_coefficients += coefficient

        details_matieres.append({
            'matiere': matiere,
            'moyenne_annuelle': result['moyenne_annuelle'],
            'moyennes_periodes': result['moyennes_periodes'],
            'moyenne': moyenne_matiere if result['moyenne_annuelle'] is not None else None,
            'coefficient': coefficient if niveau != 'PRIMAIRE' else 1,
            'points': points,
        })

    # Calculer la moyenne générale annuelle (arrondi final seulement)
    moyenne_generale = None
    if total_coefficients and total_coefficients > 0:
        try:
            moyenne_generale = _arrondir_deux_decimales(total_points / total_coefficients)
        except (ZeroDivisionError, ValueError, TypeError):
            moyenne_generale = None

    return {
        'moyenne_generale': moyenne_generale,
        'total_points': float(total_points) if total_points > 0 else 0,
        'total_coefficients': float(total_coefficients),
        'details_matieres': details_matieres,
        'moyennes_periodes': moyennes_generales_periodes,
        'niveau': niveau,
        'appreciations_only': False,
    }


def calculer_bulletin_intelligent(eleve, matiere, periode, system_type):
    """
    Fonction centralisée intelligente pour calculer les données d'une matière
    selon le type de système sélectionné.
    
    SOURCES DE DONNÉES:
    - MENSUEL: NoteMensuelle (note du mois sélectionné)
    - TRIMESTRIEL: NoteMensuelle (moyenne des mois du trimestre) + CompositionNote
    - SEMESTRIEL: NoteMensuelle (moyenne des mois du semestre) + CompositionNote
    - ANNUEL_TRIMESTRIEL: Moyenne des 3 trimestres (T1+T2+T3)/3
    - ANNUEL_SEMESTRIEL: Moyenne des 2 semestres (S1+S2)/2
    
    FORMULES:
    - Mensuel: Moyenne = Note du mois
    - Trimestriel/Semestriel: Primaire = composition, Secondaire = 40% cours + 60% composition
    - Annuel Trimestriel: Moyenne = (Moy T1 + Moy T2 + Moy T3) / 3
    - Annuel Semestriel: Moyenne = (Moy S1 + Moy S2) / 2
    
    Args:
        eleve: Instance Eleve
        matiere: Instance MatiereNote
        periode: Code de la période (ex: 'OCTOBRE', 'TRIMESTRE_1', 'ANNUEL_TRIM')
        system_type: Type de système ('mensuel', 'trimestre', 'semestre', 'annuel_trimestriel', 'annuel_semestriel')
    
    Returns:
        dict avec toutes les données nécessaires pour l'affichage du bulletin
    """
    # Détecter le niveau scolaire pour les coefficients
    niveau = detecter_niveau_scolaire(matiere.classe.nom if hasattr(matiere.classe, 'nom') else '')
    est_primaire = (niveau == 'PRIMAIRE')
    
    # Déterminer le coefficient effectif
    if est_primaire:
        coefficient_effectif = Decimal('1')
    else:
        coefficient_effectif = matiere.coefficient if matiere.coefficient and matiere.coefficient > 0 else Decimal('1')
    
    # Initialiser les résultats
    result = {
        'matiere': matiere,
        'moyenne_continue': None,
        'note_composition': None,
        'moyenne': None,
        'moyennes_mensuelles': [],  # Pour affichage détaillé
        'coefficient': float(coefficient_effectif),
        'points': None,
        'niveau': niveau,
        'est_primaire': est_primaire,
    }
    
    # ============================================================
    # SYSTÈME MENSUEL: Note du mois uniquement
    # ============================================================
    if system_type == 'mensuel':
        note_mensuelle = NoteMensuelle.objects.filter(
            eleve=eleve,
            matiere=matiere,
            mois=periode,
            annee_scolaire=matiere.classe.annee_scolaire
        ).first()
        if note_mensuelle and not note_mensuelle.absent and note_mensuelle.note is not None:
            _b = bonus_suivi(eleve.id, matiere.id, periode, matiere.classe.annee_scolaire)
            _val = _appliquer_bonus(float(note_mensuelle.note), _b)
            result['moyenne_continue'] = _val
            result['moyenne'] = _val
    
    # ============================================================
    # SYSTÈME TRIMESTRIEL: Moyenne des mois + Composition
    # ============================================================
    elif system_type in ['trimestre', 'trimestriel']:
        # Déterminer les mois du trimestre
        mois_mapping = {
            'TRIMESTRE_1': ['OCTOBRE', 'NOVEMBRE'],  # Décembre = Composition
            'TRIMESTRE_2': ['JANVIER', 'FEVRIER'],   # Mars = Composition
            'TRIMESTRE_3': ['AVRIL', 'MAI'],         # Juin = Composition
        }
        mois_periode = mois_mapping.get(periode, [])
        
        # Calculer la moyenne continue des mois
        if mois_periode:
            total_notes = Decimal('0')
            count_notes = 0
            moyennes_detail = []
            
            for mois in mois_periode:
                note_mensuelle = NoteMensuelle.objects.filter(
                    eleve=eleve,
                    matiere=matiere,
                    mois=mois,
                    annee_scolaire=matiere.classe.annee_scolaire
                ).first()
                if note_mensuelle and not note_mensuelle.absent and note_mensuelle.note is not None:
                    _b = bonus_suivi(eleve.id, matiere.id, mois, matiere.classe.annee_scolaire)
                    _val = _appliquer_bonus(float(note_mensuelle.note), _b)
                    total_notes += Decimal(str(_val))
                    count_notes += 1
                    moyennes_detail.append({
                        'libelle': mois[:3] + '.',
                        'moyenne': _val,
                        'absent': False
                    })
                else:
                    moyennes_detail.append({
                        'libelle': mois[:3] + '.',
                        'moyenne': None,
                        'absent': note_mensuelle.absent if note_mensuelle else True
                    })
            
            result['moyennes_mensuelles'] = moyennes_detail
            
            if count_notes > 0:
                result['moyenne_continue'] = float(total_notes / count_notes)
        
        # Récupérer la note de composition
        compo = CompositionNote.objects.filter(
            eleve=eleve,
            matiere=matiere,
            periode=periode,
            annee_scolaire=matiere.classe.annee_scolaire
        ).first()
        if compo and not compo.absent and compo.note is not None:
            result['note_composition'] = float(compo.note)

        # RÈGLE STRICTE: la classe a composé mais pas cet élève -> 0
        if result['note_composition'] is None and _matiere_a_compositions(matiere, periode, 'trimestre'):
            result['note_composition'] = 0.0

        # Calculer la moyenne finale - LOGIQUE ADAPTATIVE
        # CAS 1: Les deux existent -> formule guineenne par niveau
        # CAS 2: Seulement composition (école sans notes mensuelles) → Utiliser directement
        # CAS 3: Seulement notes mensuelles → Utiliser directement
        moyenne_calculee = calculer_moyenne_periode_guineenne(
            result['moyenne_continue'],
            result['note_composition'],
            'PRIMAIRE' if est_primaire else 'SECONDAIRE'
        )
        if moyenne_calculee is not None:
            result['moyenne'] = round(moyenne_calculee, 2)
    
    # ============================================================
    # SYSTÈME SEMESTRIEL: Moyenne des mois + Composition
    # ============================================================
    elif system_type in ['semestre', 'semestriel']:
        # Déterminer les mois du semestre
        mois_mapping = {
            'SEMESTRE_1': ['OCTOBRE', 'NOVEMBRE', 'DECEMBRE', 'JANVIER'],  # Février = Composition
            'SEMESTRE_2': ['MARS', 'AVRIL', 'MAI'],                        # Juin = Composition
        }
        mois_periode = mois_mapping.get(periode, [])
        
        # Calculer la moyenne continue des mois
        if mois_periode:
            total_notes = Decimal('0')
            count_notes = 0
            moyennes_detail = []
            
            for mois in mois_periode:
                note_mensuelle = NoteMensuelle.objects.filter(
                    eleve=eleve,
                    matiere=matiere,
                    mois=mois,
                    annee_scolaire=matiere.classe.annee_scolaire
                ).first()
                if note_mensuelle and not note_mensuelle.absent and note_mensuelle.note is not None:
                    _b = bonus_suivi(eleve.id, matiere.id, mois, matiere.classe.annee_scolaire)
                    _val = _appliquer_bonus(float(note_mensuelle.note), _b)
                    total_notes += Decimal(str(_val))
                    count_notes += 1
                    moyennes_detail.append({
                        'libelle': mois[:3] + '.',
                        'moyenne': _val,
                        'absent': False
                    })
                else:
                    moyennes_detail.append({
                        'libelle': mois[:3] + '.',
                        'moyenne': None,
                        'absent': note_mensuelle.absent if note_mensuelle else True
                    })
            
            result['moyennes_mensuelles'] = moyennes_detail
            
            if count_notes > 0:
                result['moyenne_continue'] = float(total_notes / count_notes)
        
        # Récupérer la note de composition
        compo = CompositionNote.objects.filter(
            eleve=eleve,
            matiere=matiere,
            periode=periode,
            annee_scolaire=matiere.classe.annee_scolaire
        ).first()
        if compo and not compo.absent and compo.note is not None:
            result['note_composition'] = float(compo.note)

        # Repli: compositions saisies en trimestres mais consultation semestrielle
        if result['note_composition'] is None:
            fb = _compositions_semestre_depuis_trimestres(
                [eleve.id], [matiere.id], periode, matiere.classe.annee_scolaire
            )
            val_fb = fb.get((eleve.id, matiere.id))
            if val_fb is not None:
                result['note_composition'] = val_fb

        # RÈGLE STRICTE: la classe a composé mais pas cet élève -> 0
        if result['note_composition'] is None and _matiere_a_compositions(matiere, periode, 'semestre'):
            result['note_composition'] = 0.0

        # Calculer la moyenne finale - LOGIQUE ADAPTATIVE
        # CAS 1: Les deux existent -> formule guineenne par niveau
        # CAS 2: Seulement composition (école sans notes mensuelles) → Utiliser directement
        # CAS 3: Seulement notes mensuelles → Utiliser directement
        moyenne_calculee = calculer_moyenne_periode_guineenne(
            result['moyenne_continue'],
            result['note_composition'],
            'PRIMAIRE' if est_primaire else 'SECONDAIRE'
        )
        if moyenne_calculee is not None:
            result['moyenne'] = round(moyenne_calculee, 2)

    # ============================================================
    # SYSTÈME ANNUEL TRIMESTRIEL: (T1 + T2 + T3) / 3
    # ============================================================
    elif system_type == 'annuel_trimestriel':
        periodes_trim = ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']
        labels_trim = ['1er Trim.', '2ème Trim.', '3ème Trim.']
        moyennes_periodes = []
        
        for i, periode_code in enumerate(periodes_trim):
            # Utiliser la fonction existante pour calculer la moyenne du trimestre
            result_trim = calculer_moyenne_matiere(eleve, matiere, periode_code, 'trimestre')
            moy_trim = result_trim['moyenne_matiere']
            
            moyennes_periodes.append({
                'libelle': labels_trim[i],
                'moyenne': moy_trim,
                'absent': moy_trim is None
            })
        
        result['moyennes_mensuelles'] = moyennes_periodes
        
        # Calculer la moyenne annuelle: (T1 + T2 + T3) / 3
        moyennes_valides = [m['moyenne'] for m in moyennes_periodes if m['moyenne'] is not None]
        if moyennes_valides:
            moyennes_avec_absents = [m['moyenne'] if m['moyenne'] is not None else 0 for m in moyennes_periodes]
            result['moyenne'] = round(sum(moyennes_avec_absents) / len(moyennes_avec_absents), 2)
            result['moyenne_continue'] = result['moyenne']  # Pour compatibilité
    
    # ============================================================
    # SYSTÈME ANNUEL SEMESTRIEL: (S1 + S2) / 2
    # ============================================================
    elif system_type == 'annuel_semestriel':
        periodes_sem = ['SEMESTRE_1', 'SEMESTRE_2']
        labels_sem = ['1er Sem.', '2ème Sem.']
        moyennes_periodes = []
        
        for i, periode_code in enumerate(periodes_sem):
            # Utiliser la fonction existante pour calculer la moyenne du semestre
            result_sem = calculer_moyenne_matiere(eleve, matiere, periode_code, 'semestre')
            moy_sem = result_sem['moyenne_matiere']
            
            moyennes_periodes.append({
                'libelle': labels_sem[i],
                'moyenne': moy_sem,
                'absent': moy_sem is None
            })
        
        result['moyennes_mensuelles'] = moyennes_periodes
        
        # Calculer la moyenne annuelle: (S1 + S2) / 2
        moyennes_valides = [m['moyenne'] for m in moyennes_periodes if m['moyenne'] is not None]
        if moyennes_valides:
            moyennes_avec_absents = [m['moyenne'] if m['moyenne'] is not None else 0 for m in moyennes_periodes]
            result['moyenne'] = round(sum(moyennes_avec_absents) / len(moyennes_avec_absents), 2)
            result['moyenne_continue'] = result['moyenne']  # Pour compatibilité
    
    # ============================================================
    # CALCULER LES POINTS
    # ============================================================
    # Élève non évalué dans cette matière = note 0 par défaut
    if result['moyenne'] is None:
        result['moyenne'] = 0.0
    
    result['points'] = round(result['moyenne'] * float(coefficient_effectif), 2)
    
    return result
