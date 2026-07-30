#!/usr/bin/env python
"""
Script pour ajouter les nouveaux types de paiements groupés
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import TypePaiement

def add_combined_payment_types():
    """Ajoute les nouveaux types de paiements groupés"""
    
    print("💳 Ajout des types de paiements groupés...")
    print("=" * 50)
    
    # Types de paiements à créer
    nouveaux_types = [
        {
            'nom': 'Frais d\'inscription + Scolarité 1ère Tranche',
            'description': 'Paiement combiné des frais d\'inscription et de la première tranche de scolarité en une seule fois'
        },
        {
            'nom': 'Scolarité Annuelle',
            'description': 'Paiement de la totalité de la scolarité annuelle (toutes les tranches) en une seule fois'
        }
    ]
    
    types_crees = 0
    
    for type_data in nouveaux_types:
        type_paiement, created = TypePaiement.objects.get_or_create(
            nom=type_data['nom'],
            defaults={
                'description': type_data['description'],
                'actif': True
            }
        )
        
        if created:
            print(f"✅ Créé: {type_paiement.nom}")
            types_crees += 1
        else:
            print(f"ℹ️  Existe déjà: {type_paiement.nom}")
    
    print(f"\n📊 Résultat: {types_crees} nouveau(x) type(s) créé(s)")
    
    # Afficher tous les types de paiements disponibles
    print(f"\n📋 Types de paiements disponibles:")
    print("-" * 40)
    
    for type_paiement in TypePaiement.objects.filter(actif=True).order_by('nom'):
        status = "🟢" if type_paiement.actif else "🔴"
        print(f"{status} {type_paiement.nom}")
        if type_paiement.description:
            print(f"   📝 {type_paiement.description}")
        print()
    
    print("✅ Configuration terminée!")

if __name__ == '__main__':
    add_combined_payment_types()
