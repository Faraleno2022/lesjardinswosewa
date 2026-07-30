#!/usr/bin/env python
"""
Script pour vérifier l'école de la classe maternelle manquante
"""

import os
import sys
import django

# Configuration de l'environnement Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote
from eleves.models import Ecole

print("🔍 VÉRIFICATION DES ÉCOLES DES CLASSES MATERNELLE")
print("=" * 60)

# Récupérer l'école par défaut
ecole_defaut = Ecole.objects.first()
print(f"École par défaut : {ecole_defaut.nom if ecole_defaut else 'None'}")

# Vérifier toutes les classes maternelle
classes_maternelle = ClasseNote.objects.filter(niveau='MATERNELLE')
print(f"\n📚 Classes maternelle trouvées : {classes_maternelle.count()}")

for classe in classes_maternelle:
    nom_ecole = classe.ecole.nom if classe.ecole else "Aucune"
    meme_ecole = classe.ecole == ecole_defaut if classe.ecole and ecole_defaut else False
    print(f"  • {classe.nom} (ID: {classe.id})")
    print(f"    - École : {nom_ecole}")
    print(f"    - Niveau : '{classe.niveau}'")
    print(f"    - Même école que défaut : {meme_ecole}")
    print()

# Filtrer comme dans la commande
classes_filtrees = ClasseNote.objects.filter(
    ecole=ecole_defaut,
    niveau='MATERNELLE'
)

print(f"🎯 Classes après filtrage (école + niveau) : {classes_filtrees.count()}")
for classe in classes_filtrees:
    print(f"  • {classe.nom} (ID: {classe.id})")
