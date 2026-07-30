import re
from typing import Tuple, Optional

# Détection intelligente du niveau (PRIMAIRE / SECONDAIRE) et de la série
# À partir du nom de la classe: ex. "7ème Année", "12ème Série scientifique", "Terminale SM", "7ème Année A"

SECONDAIRE_KEYWORDS = {
    'COLLEGE': [r"\b7(?:eme|ème)\b", r"\b8(?:eme|ème)\b", r"\b9(?:eme|ème)\b", r"\b10(?:eme|ème)\b"],
    'LYCEE': [r"\b11(?:eme|ème)\b", r"\b12(?:eme|ème)\b", r"\bterminale\b", r"\bT\.?[\s-]*erm?\b"],
}

PRIMAIRE_KEYWORDS = [
    r"\bCP\s*1\b", r"\bCP\s*2\b",
    r"\bCE\s*1\b", r"\bCE\s*2\b",
    r"\bCM\s*1\b", r"\bCM\s*2\b",
]

SERIE_PATTERNS = [
    (r"\bs[eé]rie\s*litt[eé]raire\b", "Littéraire"),
    (r"\bs[eé]rie\s*scientifique\b", "Scientifique"),
    (r"\bSL\b", "Littéraire"),
    (r"\bSS\b", "Scientifique (SS)"),
    (r"\bSM\b", "Scientifique (SM)"),
    (r"\bSE\b", "Sciences Économiques"),
]

SUFFIX_SECTION_PATTERN = r"\b([A-Z])\b$"  # ex. "7ème Année A" -> section A


def classify_level(class_name: str) -> str:
    name = class_name.lower()
    # Primaire
    for pat in PRIMAIRE_KEYWORDS:
        if re.search(pat, name, flags=re.IGNORECASE):
            return 'PRIMAIRE'
    # Collège / Lycée
    for pat in SECONDAIRE_KEYWORDS['COLLEGE']:
        if re.search(pat, name, flags=re.IGNORECASE):
            return 'SECONDAIRE'
    for pat in SECONDAIRE_KEYWORDS['LYCEE']:
        if re.search(pat, name, flags=re.IGNORECASE):
            return 'SECONDAIRE'
    # Défaut: Secondaire si "Année" >= 7 explicite
    if re.search(r"\b(7|8|9|10|11|12|13)\s*(?:eme|ème)?\b", name, re.IGNORECASE):
        return 'SECONDAIRE'
    return 'PRIMAIRE'


def extract_serie(class_name: str) -> Optional[str]:
    name = class_name
    # Terminale sous-séries (priorité haute)
    if re.search(r"\bterminale\s*sm\b", name, re.IGNORECASE):
        return 'Scientifique (SM)'
    if re.search(r"\bterminale\s*ss\b", name, re.IGNORECASE):
        return 'Scientifique (SS)'
    if re.search(r"\bterminale\s*se\b", name, re.IGNORECASE):
        return 'Sciences Économiques (SE)'
    
    # Patterns généraux
    for pat, label in SERIE_PATTERNS:
        if re.search(pat, name, flags=re.IGNORECASE):
            return label
    return None


def extract_section(class_name: str) -> Optional[str]:
    m = re.search(SUFFIX_SECTION_PATTERN, class_name.strip())
    if m:
        return m.group(1)
    return None


def classify(class_name: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Retourne (niveau, serie, section) à partir du nom de classe."""
    niveau = classify_level(class_name)
    serie = extract_serie(class_name)
    section = extract_section(class_name)
    return niveau, serie, section
