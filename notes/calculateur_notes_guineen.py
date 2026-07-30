"""
Système Intelligent de Calcul de Notes - Éducation Guinéenne
Prend en compte tous les niveaux et combinaisons possibles
"""

from typing import List, Dict, Optional
from enum import Enum

class NiveauScolaire(Enum):
    MATERNELLE = "maternelle"
    PRIMAIRE = "primaire"
    COLLEGE = "college"
    LYCEE = "lycee"

class SystemeEvaluation(Enum):
    TRIMESTRE = "trimestre"
    SEMESTRE = "semestre"

class TypeNote(Enum):
    MENSUELLE = "mensuelle"
    COMPOSITION = "composition"
    APPRECIATION = "appreciation"

class CalculateurNotes:
    """Calculateur intelligent de notes selon les normes guinéennes"""
    
    # Pondérations pour le secondaire
    POND_COURS = 0.40
    POND_COMPOSITION = 0.60
    
    def __init__(self, niveau: NiveauScolaire, systeme: SystemeEvaluation):
        self.niveau = niveau
        self.systeme = systeme
        self.notation_max = self._get_notation_max()
        
    def _get_notation_max(self) -> Optional[int]:
        """Retourne la notation maximale selon le niveau"""
        if self.niveau == NiveauScolaire.MATERNELLE:
            return None  # Appréciations
        elif self.niveau == NiveauScolaire.PRIMAIRE:
            return 10
        else:  # Collège ou Lycée
            return 20
    
    def calculer_moyenne_mensuelle(self, notes_mois: List[float]) -> float:
        """Calcule la moyenne des notes d'un mois"""
        if not notes_mois:
            return 0.0
        return sum(notes_mois) / len(notes_mois)
    
    def calculer_moyenne_cours_periode(self, notes_mensuelles: Dict[str, List[float]]) -> float:
        """
        Calcule la moyenne de cours d'une période (trimestre ou semestre)
        notes_mensuelles: {'octobre': [14, 15], 'novembre': [12, 14], ...}
        """
        moyennes_mois = []
        for mois, notes in notes_mensuelles.items():
            if notes:
                moyennes_mois.append(self.calculer_moyenne_mensuelle(notes))
        
        if not moyennes_mois:
            return 0.0
        return sum(moyennes_mois) / len(moyennes_mois)
    
    def calculer_note_periode_secondaire(self, 
                                        notes_mensuelles: Dict[str, List[float]], 
                                        composition: float) -> float:
        """
        Calcule la note d'une période pour le secondaire
        Formule: (Moyenne Cours × 40%) + (Composition × 60%)
        """
        moyenne_cours = self.calculer_moyenne_cours_periode(notes_mensuelles)
        note_periode = (moyenne_cours * self.POND_COURS) + (composition * self.POND_COMPOSITION)
        return round(note_periode, 2)
    
    def calculer_moyenne_annuelle_matiere_primaire(self, compositions: List[float]) -> float:
        """
        Calcule la moyenne annuelle pour une matière au primaire
        Moyenne simple des 3 compositions trimestrielles
        """
        if not compositions or len(compositions) != 3:
            raise ValueError("Le primaire nécessite exactement 3 compositions trimestrielles")
        return round(sum(compositions) / len(compositions), 2)
    
    def calculer_moyenne_annuelle_matiere_secondaire(self, notes_periodes: List[float]) -> float:
        """
        Calcule la moyenne annuelle pour une matière au secondaire
        - Système semestriel: moyenne de 2 notes semestrielles
        - Système trimestriel: moyenne de 3 notes trimestrielles
        """
        nb_periodes_attendues = 2 if self.systeme == SystemeEvaluation.SEMESTRE else 3
        
        if not notes_periodes or len(notes_periodes) != nb_periodes_attendues:
            raise ValueError(f"Nombre de périodes incorrect. Attendu: {nb_periodes_attendues}")
        
        return round(sum(notes_periodes) / len(notes_periodes), 2)
    
    def calculer_moyenne_generale_annuelle(self, resultats_matieres: List[Dict]) -> float:
        """
        Calcule la moyenne générale annuelle
        resultats_matieres: [
            {'matiere': 'Maths', 'moyenne': 13.61, 'coefficient': 5},
            {'matiere': 'Français', 'moyenne': 12.75, 'coefficient': 4},
            ...
        ]
        """
        if self.niveau == NiveauScolaire.PRIMAIRE:
            # Primaire: moyenne simple (pas de coefficients)
            moyennes = [r['moyenne'] for r in resultats_matieres]
            return round(sum(moyennes) / len(moyennes), 2)
        
        else:  # Secondaire avec coefficients
            total_points = sum(r['moyenne'] * r['coefficient'] for r in resultats_matieres)
            total_coef = sum(r['coefficient'] for r in resultats_matieres)
            return round(total_points / total_coef, 2)


class EleveSecondaire:
    """Gestion complète d'un élève du secondaire"""
    
    def __init__(self, nom: str, prenom: str, classe: str, systeme: SystemeEvaluation):
        self.nom = nom
        self.prenom = prenom
        self.classe = classe
        self.systeme = systeme
        self.calculateur = CalculateurNotes(
            NiveauScolaire.COLLEGE if "ème" in classe else NiveauScolaire.LYCEE,
            systeme
        )
        self.matieres = {}
    
    def ajouter_matiere(self, nom: str, coefficient: int):
        """Ajoute une matière avec son coefficient"""
        self.matieres[nom] = {
            'coefficient': coefficient,
            'periodes': []
        }
    
    def ajouter_notes_periode(self, matiere: str, 
                             notes_mensuelles: Dict[str, List[float]], 
                             composition: float):
        """Ajoute les notes d'une période (trimestre ou semestre)"""
        if matiere not in self.matieres:
            raise ValueError(f"Matière {matiere} non trouvée")
        
        note_periode = self.calculateur.calculer_note_periode_secondaire(
            notes_mensuelles, composition
        )
        self.matieres[matiere]['periodes'].append(note_periode)
    
    def calculer_moyenne_matiere(self, matiere: str) -> float:
        """Calcule la moyenne annuelle d'une matière"""
        if matiere not in self.matieres:
            raise ValueError(f"Matière {matiere} non trouvée")
        
        notes_periodes = self.matieres[matiere]['periodes']
        return self.calculateur.calculer_moyenne_annuelle_matiere_secondaire(notes_periodes)
    
    def calculer_moyenne_generale(self) -> Dict:
        """Calcule la moyenne générale annuelle et retourne le bulletin complet"""
        resultats = []
        
        for matiere, data in self.matieres.items():
            moyenne = self.calculer_moyenne_matiere(matiere)
            resultats.append({
                'matiere': matiere,
                'moyenne': moyenne,
                'coefficient': data['coefficient'],
                'points': round(moyenne * data['coefficient'], 2)
            })
        
        moyenne_generale = self.calculateur.calculer_moyenne_generale_annuelle(resultats)
        
        return {
            'eleve': f"{self.prenom} {self.nom}",
            'classe': self.classe,
            'systeme': self.systeme.value,
            'matieres': resultats,
            'moyenne_generale': moyenne_generale,
            'total_points': sum(r['points'] for r in resultats),
            'total_coefficients': sum(r['coefficient'] for r in resultats)
        }


class ElevePrimaire:
    """Gestion complète d'un élève du primaire"""
    
    def __init__(self, nom: str, prenom: str, classe: str):
        self.nom = nom
        self.prenom = prenom
        self.classe = classe
        self.calculateur = CalculateurNotes(
            NiveauScolaire.PRIMAIRE,
            SystemeEvaluation.TRIMESTRE
        )
        self.matieres = {}
    
    def ajouter_matiere(self, nom: str):
        """Ajoute une matière (sans coefficient au primaire)"""
        self.matieres[nom] = {
            'compositions': []
        }
    
    def ajouter_composition(self, matiere: str, note: float):
        """Ajoute une note de composition (sur 10)"""
        if matiere not in self.matieres:
            raise ValueError(f"Matière {matiere} non trouvée")
        
        if note < 0 or note > 10:
            raise ValueError("La note doit être entre 0 et 10 pour le primaire")
        
        self.matieres[matiere]['compositions'].append(note)
    
    def calculer_moyenne_matiere(self, matiere: str) -> float:
        """Calcule la moyenne annuelle d'une matière"""
        if matiere not in self.matieres:
            raise ValueError(f"Matière {matiere} non trouvée")
        
        compositions = self.matieres[matiere]['compositions']
        return self.calculateur.calculer_moyenne_annuelle_matiere_primaire(compositions)
    
    def calculer_moyenne_generale(self) -> Dict:
        """Calcule la moyenne générale annuelle"""
        resultats = []
        
        for matiere in self.matieres.keys():
            moyenne = self.calculer_moyenne_matiere(matiere)
            resultats.append({
                'matiere': matiere,
                'moyenne': moyenne,
                'coefficient': None  # Pas de coefficient au primaire
            })
        
        moyenne_generale = self.calculateur.calculer_moyenne_generale_annuelle(resultats)
        
        return {
            'eleve': f"{self.prenom} {self.nom}",
            'classe': self.classe,
            'matieres': resultats,
            'moyenne_generale': moyenne_generale
        }


def afficher_bulletin_secondaire(bulletin: Dict):
    """Affiche un bulletin du secondaire de manière formatée"""
    print("\n" + "=" * 80)
    print(f"BULLETIN ANNUEL - {bulletin['systeme'].upper()}")
    print("=" * 80)
    print(f"Élève: {bulletin['eleve']}")
    print(f"Classe: {bulletin['classe']}")
    print("=" * 80)
    print(f"{'MATIÈRE':<30} {'MOYENNE':<10} {'COEF':<6} {'POINTS':<10}")
    print("-" * 80)
    
    for m in bulletin['matieres']:
        print(f"{m['matiere']:<30} {m['moyenne']:<10.2f} {m['coefficient']:<6} {m['points']:<10.2f}")
    
    print("=" * 80)
    print(f"TOTAL POINTS: {bulletin['total_points']:.2f} / {bulletin['total_coefficients']} coef")
    print(f"MOYENNE GÉNÉRALE: {bulletin['moyenne_generale']:.2f}/20")
    print("=" * 80)


def afficher_bulletin_primaire(bulletin: Dict):
    """Affiche un bulletin du primaire de manière formatée"""
    print("\n" + "=" * 80)
    print("BULLETIN ANNUEL - PRIMAIRE")
    print("=" * 80)
    print(f"Élève: {bulletin['eleve']}")
    print(f"Classe: {bulletin['classe']}")
    print("=" * 80)
    print(f"{'MATIÈRE':<30} {'MOYENNE':<10}")
    print("-" * 80)
    
    for m in bulletin['matieres']:
        print(f"{m['matiere']:<30} {m['moyenne']:<10.2f}")
    
    print("=" * 80)
    print(f"MOYENNE GÉNÉRALE: {bulletin['moyenne_generale']:.2f}/10")
    print("=" * 80)


# ============= EXEMPLES D'UTILISATION =============

def exemple_secondaire_semestriel():
    """Exemple complet: Élève de collège en système semestriel"""
    print("=" * 80)
    print("EXEMPLE: SECONDAIRE - SYSTÈME SEMESTRIEL")
    print("=" * 80)
    
    # Création de l'élève
    eleve = EleveSecondaire("CAMARA", "Mariama", "9ème Année", SystemeEvaluation.SEMESTRE)
    
    # Ajout des matières avec coefficients
    eleve.ajouter_matiere("Mathématiques", 4)
    eleve.ajouter_matiere("Français", 4)
    eleve.ajouter_matiere("Anglais", 2)
    eleve.ajouter_matiere("Sciences Physiques", 2)
    
    # MATHÉMATIQUES
    # Semestre 1
    notes_s1_maths = {
        'octobre': [13, 15],
        'novembre': [12, 14],
        'decembre': [16, 15],
        'janvier': [11, 13, 14]
    }
    eleve.ajouter_notes_periode("Mathématiques", notes_s1_maths, 12)
    
    # Semestre 2
    notes_s2_maths = {
        'mars': [15, 14],
        'avril': [16, 15],
        'mai': [17, 16],
        'juin': [14, 15]
    }
    eleve.ajouter_notes_periode("Mathématiques", notes_s2_maths, 14)
    
    # FRANÇAIS
    notes_s1_fr = {
        'octobre': [12, 13],
        'novembre': [11, 12],
        'decembre': [13, 14],
        'janvier': [12, 13]
    }
    eleve.ajouter_notes_periode("Français", notes_s1_fr, 11)
    
    notes_s2_fr = {
        'mars': [13, 14],
        'avril': [14, 15],
        'mai': [15, 14],
        'juin': [13, 14]
    }
    eleve.ajouter_notes_periode("Français", notes_s2_fr, 13)
    
    # ANGLAIS
    notes_s1_ang = {
        'octobre': [14, 15],
        'novembre': [13, 14],
        'decembre': [15, 16],
        'janvier': [14, 15]
    }
    eleve.ajouter_notes_periode("Anglais", notes_s1_ang, 13)
    
    notes_s2_ang = {
        'mars': [15, 16],
        'avril': [14, 15],
        'mai': [16, 15],
        'juin': [15, 16]
    }
    eleve.ajouter_notes_periode("Anglais", notes_s2_ang, 14)
    
    # SCIENCES PHYSIQUES
    notes_s1_phy = {
        'octobre': [11, 12],
        'novembre': [10, 11],
        'decembre': [12, 13],
        'janvier': [11, 12]
    }
    eleve.ajouter_notes_periode("Sciences Physiques", notes_s1_phy, 10)
    
    notes_s2_phy = {
        'mars': [12, 13],
        'avril': [13, 14],
        'mai': [14, 13],
        'juin': [12, 13]
    }
    eleve.ajouter_notes_periode("Sciences Physiques", notes_s2_phy, 12)
    
    # Calcul et affichage du bulletin
    bulletin = eleve.calculer_moyenne_generale()
    afficher_bulletin_secondaire(bulletin)


def exemple_secondaire_trimestriel():
    """Exemple complet: Élève de lycée en système trimestriel"""
    print("\n" + "=" * 80)
    print("EXEMPLE: SECONDAIRE - SYSTÈME TRIMESTRIEL")
    print("=" * 80)
    
    # Création de l'élève
    eleve = EleveSecondaire("SOW", "Ibrahima", "11ème Année Sciences", SystemeEvaluation.TRIMESTRE)
    
    # Ajout des matières
    eleve.ajouter_matiere("Mathématiques", 5)
    eleve.ajouter_matiere("Physique-Chimie", 4)
    eleve.ajouter_matiere("SVT", 3)
    
    # MATHÉMATIQUES - 3 trimestres
    # Trimestre 1
    notes_t1_maths = {
        'octobre': [14, 15],
        'novembre': [13, 14],
        'decembre': [15, 16]
    }
    eleve.ajouter_notes_periode("Mathématiques", notes_t1_maths, 13)
    
    # Trimestre 2
    notes_t2_maths = {
        'janvier': [12, 13],
        'fevrier': [14, 15],
        'mars': [16, 15]
    }
    eleve.ajouter_notes_periode("Mathématiques", notes_t2_maths, 14)
    
    # Trimestre 3
    notes_t3_maths = {
        'avril': [15, 16],
        'mai': [17, 16],
        'juin': [14, 15]
    }
    eleve.ajouter_notes_periode("Mathématiques", notes_t3_maths, 15)
    
    # PHYSIQUE-CHIMIE
    notes_t1_phy = {
        'octobre': [14, 12],
        'novembre': [15, 16],
        'decembre': [13, 14]
    }
    eleve.ajouter_notes_periode("Physique-Chimie", notes_t1_phy, 11)
    
    notes_t2_phy = {
        'janvier': [13, 14],
        'fevrier': [15, 14],
        'mars': [12, 13]
    }
    eleve.ajouter_notes_periode("Physique-Chimie", notes_t2_phy, 12)
    
    notes_t3_phy = {
        'avril': [14, 15],
        'mai': [16, 15],
        'juin': [13, 14]
    }
    eleve.ajouter_notes_periode("Physique-Chimie", notes_t3_phy, 14)
    
    # SVT
    notes_t1_svt = {
        'octobre': [12, 13],
        'novembre': [14, 13],
        'decembre': [15, 14]
    }
    eleve.ajouter_notes_periode("SVT", notes_t1_svt, 12)
    
    notes_t2_svt = {
        'janvier': [13, 14],
        'fevrier': [15, 14],
        'mars': [14, 15]
    }
    eleve.ajouter_notes_periode("SVT", notes_t2_svt, 13)
    
    notes_t3_svt = {
        'avril': [14, 15],
        'mai': [16, 15],
        'juin': [15, 16]
    }
    eleve.ajouter_notes_periode("SVT", notes_t3_svt, 15)
    
    # Calcul et affichage du bulletin
    bulletin = eleve.calculer_moyenne_generale()
    afficher_bulletin_secondaire(bulletin)


def exemple_primaire():
    """Exemple complet: Élève du primaire"""
    print("\n" + "=" * 80)
    print("EXEMPLE: PRIMAIRE")
    print("=" * 80)
    
    # Création de l'élève
    eleve = ElevePrimaire("DIALLO", "Fatou", "4ème Année")
    
    # Ajout des matières
    eleve.ajouter_matiere("Français")
    eleve.ajouter_matiere("Mathématiques")
    eleve.ajouter_matiere("Histoire-Géographie")
    eleve.ajouter_matiere("Sciences")
    
    # Ajout des compositions (3 par matière)
    # FRANÇAIS
    eleve.ajouter_composition("Français", 7.5)   # Composition 1
    eleve.ajouter_composition("Français", 8.0)   # Composition 2
    eleve.ajouter_composition("Français", 8.5)   # Composition 3
    
    # MATHÉMATIQUES
    eleve.ajouter_composition("Mathématiques", 8.0)
    eleve.ajouter_composition("Mathématiques", 7.5)
    eleve.ajouter_composition("Mathématiques", 9.0)
    
    # HISTOIRE-GÉOGRAPHIE
    eleve.ajouter_composition("Histoire-Géographie", 7.0)
    eleve.ajouter_composition("Histoire-Géographie", 7.5)
    eleve.ajouter_composition("Histoire-Géographie", 8.0)
    
    # SCIENCES
    eleve.ajouter_composition("Sciences", 8.5)
    eleve.ajouter_composition("Sciences", 9.0)
    eleve.ajouter_composition("Sciences", 8.0)
    
    # Calcul et affichage du bulletin
    bulletin = eleve.calculer_moyenne_generale()
    afficher_bulletin_primaire(bulletin)


def exemple_complet():
    """Lance tous les exemples"""
    exemple_secondaire_semestriel()
    exemple_secondaire_trimestriel()
    exemple_primaire()
    
    print("\n" + "=" * 80)
    print("SYSTÈME COMPLET OPÉRATIONNEL ✅")
    print("=" * 80)
    print("\nCaractéristiques:")
    print("  • Primaire: notation sur /10, moyenne simple")
    print("  • Secondaire: notation sur /20, moyennes pondérées")
    print("  • Système semestriel: 2 périodes par an")
    print("  • Système trimestriel: 3 périodes par an")
    print("  • Calcul: 40% cours + 60% composition")
    print("  • Moyennes avec coefficients (secondaire)")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    exemple_complet()
