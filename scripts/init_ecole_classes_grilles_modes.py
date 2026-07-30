#!/usr/bin/env python
"""
Initialisation des données de base:
- École principale
- Quelques Classes (niveaux clés) pour une année scolaire
- Grilles tarifaires par niveau (montants vus dans l'UI)
- Modes de paiement
- Types de paiement

Idempotent: utilise get_or_create().
"""
import os
import sys
from decimal import Decimal

import django

# Configuration Django
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecole_moderne.settings")
django.setup()

from eleves.models import Ecole, Classe, GrilleTarifaire  # noqa: E402
from paiements.models import ModePaiement, TypePaiement  # noqa: E402


ANNEE_SCOLAIRE = os.environ.get("ANNEE_SCOLAIRE", "2025-2026")
ECOLE_NOM = os.environ.get("ECOLE_NOM", "GROUPE SCOLAIRE myschool-SONFONIA")

# Montants par défaut (reprennent l'exemple de l'UI total 1 730 000 GNF)
FRAIS_INSCRIPTION = Decimal("30000")
TRANCHE_1 = Decimal("800000")
TRANCHE_2 = Decimal("500000")
TRANCHE_3 = Decimal("400000")

# Jeux de classes à créer (nom, niveau, code_matricule facultatif)
CLASSES_A_CREER = [
    ("1ère Année", "PRIMAIRE_1", "PN1"),
    ("2ème Année", "PRIMAIRE_2", "PN2"),
    ("3ème Année", "PRIMAIRE_3", "PN3"),
]

# Modes de paiement standards
MODES_PAIEMENT = [
    ("Espèces", "Paiement en cash", 0),
    ("Chèque", "Paiement par chèque", 0),
    ("Mobile Money", "Paiement via mobile money (OM, MTN, etc.)", 0),
    ("Virement bancaire", "Transfert bancaire", 0),
]

# Types de paiement
TYPES_PAIEMENT = [
    ("Frais d'inscription", "Frais uniques d'inscription", True),
    ("Scolarité", "Règlements de scolarité (tranches)", True),
]


def ensure_ecole():
    ecole, created = Ecole.objects.get_or_create(
        nom=ECOLE_NOM,
        defaults={
            "adresse": "Sonfonia",
            "telephone": "+224000000000",
            "email": "",
            "directeur": "Directeur",
        },
    )
    print(("✅" if created else "ℹ️ "), f"École: {ecole.nom}")
    return ecole


def ensure_classes(ecole: Ecole):
    classes = []
    for nom, niveau, code in CLASSES_A_CREER:
        cls, created = Classe.objects.get_or_create(
            ecole=ecole,
            nom=nom,
            annee_scolaire=ANNEE_SCOLAIRE,
            defaults={
                "niveau": niveau,
                "code_matricule": code,
                "capacite_max": 40,
            },
        )
        print(("✅" if created else "ℹ️ "), f"Classe: {cls}")
        classes.append(cls)
    return classes


def ensure_grilles(ecole: Ecole, classes: list[Classe]):
    # Une grille par niveau (pas par classe nominale). On utilise le niveau de la classe.
    niveaux_traites = set()
    for cls in classes:
        if cls.niveau in niveaux_traites:
            continue
        niveaux_traites.add(cls.niveau)
        gr, created = GrilleTarifaire.objects.get_or_create(
            ecole=ecole,
            niveau=cls.niveau,
            annee_scolaire=ANNEE_SCOLAIRE,
            defaults={
                "frais_inscription": FRAIS_INSCRIPTION,
                "tranche_1": TRANCHE_1,
                "tranche_2": TRANCHE_2,
                "tranche_3": TRANCHE_3,
                "periode_1": "À l'inscription",
                "periode_2": "Début janvier",
                "periode_3": "Début mars",
            },
        )
        total = gr.total_avec_inscription if hasattr(gr, "total_avec_inscription") else (FRAIS_INSCRIPTION + TRANCHE_1 + TRANCHE_2 + TRANCHE_3)
        print(("✅" if created else "ℹ️ "), f"Grille: {gr} | Total: {int(total):,} GNF".replace(",", " "))


def ensure_modes():
    for nom, desc, frais in MODES_PAIEMENT:
        mode, created = ModePaiement.objects.get_or_create(
            nom=nom,
            defaults={
                "description": desc,
                "frais_supplementaires": Decimal(str(frais)),
                "actif": True,
            },
        )
        print(("✅" if created else "ℹ️ "), f"Mode paiement: {mode.nom}")


def ensure_types():
    for nom, desc, actif in TYPES_PAIEMENT:
        tp, created = TypePaiement.objects.get_or_create(
            nom=nom,
            defaults={
                "description": desc,
                "actif": bool(actif),
            },
        )
        # Si existant, on s'assure qu'il est actif et on met à jour la description si vide
        changed = False
        if not tp.actif and actif:
            tp.actif = True
            changed = True
        if desc and not tp.description:
            tp.description = desc
            changed = True
        if changed:
            tp.save()
        print(("✅" if created else "ℹ️ "), f"Type paiement: {tp.nom}")


def main():
    print("\n=== Initialisation données de base (école/classes/grilles/modes/types) ===\n")
    ecole = ensure_ecole()
    classes = ensure_classes(ecole)
    ensure_grilles(ecole, classes)
    ensure_modes()
    ensure_types()
    print("\n✅ Terminé.\n")


if __name__ == "__main__":
    main()
