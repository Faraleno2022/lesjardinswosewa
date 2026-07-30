#!/usr/bin/env python
"""Test si les modifications du bulletin ont été appliquées"""
import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent))
from load_env import *
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve

# Vérifier les élèves avec photos
print("=== VÉRIFICATION DES PHOTOS DES ÉLÈVES ===\n")
eleves_with_photo = Eleve.objects.filter(photo__isnull=False).exclude(photo__exact='')[:5]
print(f"Élèves avec photo trouvés: {eleves_with_photo.count()}")

for i, eleve in enumerate(eleves_with_photo, 1):
    print(f"\n{i}. {eleve.nom} {eleve.prenom}")
    print(f"   Photo field: {eleve.photo}")
    if eleve.photo:
        photo_path = eleve.photo.path
        print(f"   Chemin: {photo_path}")
        print(f"   Fichier existe: {os.path.exists(photo_path)}")
