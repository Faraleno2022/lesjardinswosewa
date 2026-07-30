#!/usr/bin/env python
"""
Script pour lister toutes les classes disponibles
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from notes.models import ClasseNote

print('Toutes les classes disponibles:')
print('='*60)
for classe in ClasseNote.objects.all().order_by('niveau', 'nom'):
    print(f'  ID: {classe.id} - {classe.nom} (Niveau: {classe.niveau})')

print('\nClasses contenant "SECTION":')
print('='*40)
for classe in ClasseNote.objects.filter(nom__contains='SECTION').order_by('nom'):
    print(f'  ID: {classe.id} - {classe.nom} (Niveau: {classe.niveau})')
