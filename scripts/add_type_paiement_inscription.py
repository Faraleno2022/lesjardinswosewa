#!/usr/bin/env python
"""
Script pour ajouter le type de paiement "Frais d'inscription"
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import TypePaiement

def add_type_paiement_inscription():
    """Ajoute le type de paiement pour les frais d'inscription"""
    
    print("🎓 Ajout du type de paiement 'Frais d'inscription'...")
    print("=" * 50)
    
    # Vérifier si le type existe déjà
    type_inscription, created = TypePaiement.objects.get_or_create(
        nom="Frais d'inscription",
        defaults={
            'description': "Frais d'inscription payés une seule fois lors de l'inscription de l'élève",
            'obligatoire': True,
            'recurrent': False
        }
    )
    
    if created:
        print("✅ Type de paiement 'Frais d'inscription' créé avec succès!")
    else:
        print("ℹ️  Type de paiement 'Frais d'inscription' existe déjà")
    
    print(f"   - ID: {type_inscription.id}")
    print(f"   - Nom: {type_inscription.nom}")
    print(f"   - Description: {type_inscription.description}")
    print(f"   - Obligatoire: {type_inscription.obligatoire}")
    print(f"   - Récurrent: {type_inscription.recurrent}")
    
    # Afficher tous les types de paiements disponibles
    print("\n📋 Types de paiements disponibles:")
    print("-" * 40)
    
    for type_paiement in TypePaiement.objects.all().order_by('nom'):
        status = "✅" if type_paiement.obligatoire else "⚪"
        recurrent = "🔄" if type_paiement.recurrent else "1️⃣"
        print(f"{status} {recurrent} {type_paiement.nom}")
    
    print("\n✅ Configuration terminée!")

if __name__ == '__main__':
    add_type_paiement_inscription()
