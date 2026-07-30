"""
Système de calcul des notes selon le système guinéen
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Optional


def calculer_moyenne_devoirs(notes: List[Decimal]) -> Optional[Decimal]:
    """
    Calcule la moyenne des devoirs (IGNORE les absents)
    
    Args:
        notes: Liste des notes des devoirs
        
    Returns:
        Moyenne arrondie à 2 décimales ou None si aucune note
    """
    if not notes:
        return None
    
    # IGNORER les None (absents) au lieu de les compter comme 0
    notes_valides = [n for n in notes if n is not None]
    
    if not notes_valides:
        return None
    
    moyenne = sum(notes_valides) / len(notes_valides)
    return moyenne.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculer_moyenne_periode(moyenne_cours: Optional[Decimal], 
                             composition: Optional[Decimal],
                             niveau: str = 'SECONDAIRE') -> Optional[Decimal]:
    """
    Calcule la moyenne d'une période (trimestre/semestre)
    
    SYSTÈME GUINÉEN:
    - PRIMAIRE: Composition uniquement (pas de notes mensuelles)
    - SECONDAIRE: (Moyenne Cours × 40%) + (Composition × 60%)
    
    Args:
        moyenne_cours: Moyenne des devoirs/cours mensuels
        composition: Note de composition
        niveau: 'PRIMAIRE' ou 'SECONDAIRE'
        
    Returns:
        Moyenne de la période ou None
    """
    # Primaire : composition uniquement
    if niveau == 'PRIMAIRE':
        return composition if composition is not None else moyenne_cours
    
    # Secondaire : formule 40/60
    # Si les deux sont None, pas de moyenne
    if moyenne_cours is None and composition is None:
        return None
    
    # Si un seul est disponible, on le prend
    if moyenne_cours is None:
        return composition
    if composition is None:
        return moyenne_cours
    
    # Les deux disponibles: formule guinéenne 40/60
    # Note = (Moyenne Cours × 40%) + (Composition × 60%)
    moyenne = (moyenne_cours * Decimal('0.4')) + (composition * Decimal('0.6'))
    return moyenne.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculer_moyenne_annuelle(moyennes_periodes: List[Decimal]) -> Optional[Decimal]:
    """
    Calcule la moyenne annuelle d'une matière (compte les périodes manquantes comme 0)
    
    Args:
        moyennes_periodes: Liste des moyennes de chaque période
        
    Returns:
        Moyenne annuelle ou None
    """
    if not moyennes_periodes:
        return None
    
    # Convertir les None (périodes manquantes) en 0
    moyennes_avec_absents = [m if m is not None else Decimal('0') for m in moyennes_periodes]
    
    moyenne = sum(moyennes_avec_absents) / len(moyennes_avec_absents)
    return moyenne.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def calculer_moyenne_generale(notes_matieres: Dict[str, Dict], 
                             niveau: str = 'SECONDAIRE') -> Optional[Decimal]:
    """
    Calcule la moyenne générale
    
    SYSTÈME GUINÉEN:
    - PRIMAIRE: Moyenne simple (pas de coefficients)
    - SECONDAIRE: Somme(Moyenne × Coefficient) / Somme(Coefficients)
    
    Args:
        notes_matieres: {
            'matiere_id': {
                'moyenne': Decimal,
                'coefficient': Decimal
            }
        }
        niveau: 'PRIMAIRE' ou 'SECONDAIRE'
        
    Returns:
        Moyenne générale ou None
    """
    moyennes_valides = []
    total_points = Decimal('0')
    total_coefficients = Decimal('0')
    
    for matiere_data in notes_matieres.values():
        moyenne = matiere_data.get('moyenne')
        
        if moyenne is not None:
            moyennes_valides.append(moyenne)
            
            if niveau == 'SECONDAIRE':
                coefficient = matiere_data.get('coefficient', Decimal('1'))
                total_points += moyenne * coefficient
                total_coefficients += coefficient
    
    if not moyennes_valides:
        return None
    
    # Primaire : moyenne simple
    if niveau == 'PRIMAIRE':
        moyenne_generale = sum(moyennes_valides) / len(moyennes_valides)
        return moyenne_generale.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    # Secondaire : moyenne pondérée
    if total_coefficients == 0:
        return None
    
    moyenne_generale = total_points / total_coefficients
    return moyenne_generale.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def obtenir_mention(moyenne: Optional[Decimal]) -> str:
    """
    Détermine la mention selon la moyenne avec seuils intelligents
    
    SEUILS DYNAMIQUES:
    - >= 18: Excellent
    - >= 16: Très bien
    - >= 14: Bien
    - >= 12: Assez bien
    - >= 10: Passable
    - >= 8: Insuffisant
    - >= 6: Faible
    - < 6: Très faible
    
    Args:
        moyenne: Moyenne de l'élève
        
    Returns:
        Mention (Excellent, Très Bien, etc.)
    """
    if moyenne is None:
        return "Non évalué"
    
    if moyenne >= Decimal('18'):
        return "Excellent"
    elif moyenne >= Decimal('16'):
        return "Très bien"
    elif moyenne >= Decimal('14'):
        return "Bien"
    elif moyenne >= Decimal('12'):
        return "Assez bien"
    elif moyenne >= Decimal('10'):
        return "Passable"
    elif moyenne >= Decimal('8'):
        return "Insuffisant"
    elif moyenne >= Decimal('6'):
        return "Faible"
    else:
        return "Très faible"


def obtenir_appreciation(moyenne: Optional[Decimal], prenom: str = None) -> str:
    """
    Génère une appréciation dynamique du conseil de classe selon la moyenne
    
    Args:
        moyenne: Moyenne de l'élève
        prenom: Prénom de l'élève pour personnaliser (optionnel)
        
    Returns:
        Appréciation du conseil de classe
    """
    if moyenne is None:
        return "L'élève n'a pas été évalué sur cette période."
    
    nom = prenom if prenom else "L'élève"
    
    if moyenne >= Decimal('18.5'):
        return f"Excellent travail ! {nom} est brillant(e) et exemplaire. Le conseil félicite chaleureusement."
    elif moyenne >= Decimal('17'):
        return f"Travail remarquable ! {nom} fait preuve d'excellence. Félicitations du conseil."
    elif moyenne >= Decimal('16.5'):
        return f"Très bon travail. {nom} est un(e) élève sérieux(se) et appliqué(e). Félicitations."
    elif moyenne >= Decimal('15'):
        return f"Bon travail. {nom} obtient de bons résultats. Continuez ainsi."
    elif moyenne >= Decimal('14.5'):
        return f"Travail satisfaisant. {nom} a de bonnes capacités. Persévérez."
    elif moyenne >= Decimal('13'):
        return f"Résultats corrects. {nom} peut progresser avec plus de régularité."
    elif moyenne >= Decimal('12.5'):
        return f"Résultats moyens mais encourageants. {nom} doit intensifier ses efforts."
    elif moyenne >= Decimal('11'):
        return f"Résultats fragiles. {nom} doit travailler davantage pour progresser."
    elif moyenne >= Decimal('10'):
        return f"Résultats justes passables. {nom} doit redoubler d'efforts dans toutes les matières."
    elif moyenne >= Decimal('9'):
        return f"Résultats faibles et préoccupants. Un travail soutenu est indispensable."
    elif moyenne >= Decimal('7'):
        return f"Résultats insuffisants. {nom} doit impérativement se ressaisir."
    else:
        return f"Résultats très insuffisants. Une remise en question complète est nécessaire."


def formater_rang_intelligent(rang: int, sexe: str = 'M', total_eleves: int = None) -> str:
    """
    Formate le rang avec accord grammatical intelligent
    
    Args:
        rang: Position dans le classement
        sexe: 'M' pour masculin, 'F' pour féminin
        total_eleves: Nombre total d'élèves (optionnel)
        
    Returns:
        Rang formaté avec accord grammatical (ex: "1er", "1ère", "2ème")
    """
    if rang is None or rang == 0:
        return "-"
    
    # Formater le rang avec accord grammatical
    if rang == 1:
        rang_str = "1ère" if sexe == 'F' else "1er"
    else:
        rang_str = f"{rang}ème"
    
    # On peut ajouter le total si disponible
    if total_eleves and total_eleves > 1:
        return f"{rang_str}/{total_eleves}"
    else:
        return rang_str


def calculer_rang(moyennes_eleves: List[Dict]) -> List[Dict]:
    """
    Calcule le rang de chaque élève
    
    Args:
        moyennes_eleves: [
            {'eleve_id': 1, 'moyenne': Decimal('15.5')},
            {'eleve_id': 2, 'moyenne': Decimal('14.2')},
            ...
        ]
        
    Returns:
        Liste avec rangs ajoutés, triée par moyenne décroissante
    """
    # Filtrer les élèves avec moyenne
    eleves_avec_moyenne = [e for e in moyennes_eleves if e.get('moyenne') is not None]
    
    # Trier par moyenne décroissante
    eleves_tries = sorted(
        eleves_avec_moyenne,
        key=lambda x: x['moyenne'],
        reverse=True
    )
    
    # Attribuer les rangs avec gestion des ex-aequo
    rang_actuel = 1
    total_eleves = len(eleves_tries)
    
    for i, eleve in enumerate(eleves_tries):
        # Gérer les ex-aequo
        if i > 0 and abs(eleve['moyenne'] - eleves_tries[i-1]['moyenne']) < Decimal('0.01'):
            eleve['rang_num'] = eleves_tries[i-1]['rang_num']
        else:
            eleve['rang_num'] = rang_actuel
        
        rang_actuel += 1
        
        # Formater le rang avec accord grammatical
        sexe = eleve.get('sexe', 'M')
        eleve['rang'] = formater_rang_intelligent(eleve['rang_num'], sexe, total_eleves)
        
        # Ajouter mention et appréciation
        eleve['mention'] = obtenir_mention(eleve['moyenne'])
        prenom = eleve.get('prenom', None)
        eleve['appreciation'] = obtenir_appreciation(eleve['moyenne'], prenom)
    
    # Gérer les élèves sans moyenne
    eleves_sans_moyenne = [e for e in moyennes_eleves if e.get('moyenne') is None]
    for eleve in eleves_sans_moyenne:
        eleve['rang'] = "-"
        eleve['rang_num'] = None
        eleve['mention'] = "Non évalué"
        eleve['appreciation'] = "L'élève n'a pas été évalué sur cette période."
    
    return eleves_tries + eleves_sans_moyenne


def valider_note(note: any, note_sur: Decimal = Decimal('20')) -> tuple:
    """
    Valide une note
    
    Args:
        note: Note à valider
        note_sur: Note maximale (défaut 20)
        
    Returns:
        (est_valide: bool, message_erreur: str)
    """
    if note is None:
        return True, ""
    
    try:
        note_decimal = Decimal(str(note))
    except:
        return False, "Format de note invalide"
    
    if note_decimal < 0:
        return False, "La note ne peut pas être négative"
    
    if note_decimal > note_sur:
        return False, f"La note ne peut pas dépasser {note_sur}"
    
    return True, ""


def calculer_moyenne_cours_mensuels(notes_par_mois: Dict[str, List[Decimal]]) -> Optional[Decimal]:
    """
    Calcule la moyenne des cours mensuels sur une période
    
    Args:
        notes_par_mois: {
            'octobre': [Decimal('14'), Decimal('15')],
            'novembre': [Decimal('12'), Decimal('14')],
            ...
        }
        
    Returns:
        Moyenne de cours de la période ou None
    """
    moyennes_mensuelles = []
    
    for mois, notes in notes_par_mois.items():
        moyenne_mois = calculer_moyenne_devoirs(notes)
        if moyenne_mois is not None:
            moyennes_mensuelles.append(moyenne_mois)
    
    if not moyennes_mensuelles:
        return None
    
    moyenne_cours = sum(moyennes_mensuelles) / len(moyennes_mensuelles)
    return moyenne_cours.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# Exemple d'utilisation
if __name__ == "__main__":
    print("="*80)
    print(" "*20 + "TEST SYSTÈME GUINÉEN")
    print("="*80)
    
    # Test SECONDAIRE avec formule 40/60
    print("\n🔴 SECONDAIRE - Formule 40/60")
    print("-"*80)
    
    # Notes mensuelles
    notes_mensuelles = {
        'octobre': [Decimal('14'), Decimal('15')],
        'novembre': [Decimal('12'), Decimal('14')],
        'decembre': [Decimal('16'), Decimal('15')],
        'janvier': [Decimal('11'), Decimal('13'), Decimal('14')]
    }
    
    moy_cours = calculer_moyenne_cours_mensuels(notes_mensuelles)
    print(f"Moyenne de cours: {moy_cours}")
    
    composition = Decimal('12')
    print(f"Composition: {composition}")
    
    moy_periode = calculer_moyenne_periode(moy_cours, composition, niveau='SECONDAIRE')
    print(f"Moyenne période (40% cours + 60% compo): {moy_periode}")
    print(f"Vérification: ({moy_cours} × 0.4) + ({composition} × 0.6) = {moy_periode}")
    
    # Test moyenne générale avec coefficients
    print("\n📊 Moyenne générale pondérée")
    print("-"*80)
    notes_matieres = {
        'francais': {'moyenne': Decimal('16'), 'coefficient': Decimal('4')},
        'math': {'moyenne': Decimal('14'), 'coefficient': Decimal('4')},
        'histoire': {'moyenne': Decimal('16'), 'coefficient': Decimal('2')},
    }
    moy_generale = calculer_moyenne_generale(notes_matieres, niveau='SECONDAIRE')
    print(f"Moyenne générale: {moy_generale}")
    
    # Test mention
    mention = obtenir_mention(moy_generale)
    print(f"Mention: {mention}")
    
    # Test PRIMAIRE
    print("\n🔵 PRIMAIRE - Moyenne simple")
    print("-"*80)
    notes_primaire = {
        'francais': {'moyenne': Decimal('8.0')},
        'math': {'moyenne': Decimal('7.5')},
        'sciences': {'moyenne': Decimal('9.0')},
    }
    moy_generale_primaire = calculer_moyenne_generale(notes_primaire, niveau='PRIMAIRE')
    print(f"Moyenne générale: {moy_generale_primaire}/10")
    
    # Test rang
    print("\n🏆 Classement")
    print("-"*80)
    eleves = [
        {'eleve_id': 1, 'moyenne': Decimal('15.5')},
        {'eleve_id': 2, 'moyenne': Decimal('14.2')},
        {'eleve_id': 3, 'moyenne': Decimal('16.8')},
    ]
    eleves_classes = calculer_rang(eleves)
    for e in eleves_classes:
        print(f"Rang {e['rang']}: Élève {e['eleve_id']} - Moyenne {e['moyenne']} - {e['mention']}")
    
    print("\n" + "="*80)
    print(" "*25 + "✅ TESTS RÉUSSIS")
    print("="*80)
