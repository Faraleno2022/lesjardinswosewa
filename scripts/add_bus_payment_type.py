#!/usr/bin/env python
"""
Script pour ajouter le type de paiement 'Abonnement Bus' dans le système
"""
import os
import django
import sys

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import TypePaiement, ModePaiement

def create_bus_payment_type():
    """Créer le type de paiement pour l'abonnement bus"""
    print("=== Création du type de paiement 'Abonnement Bus' ===")
    
    # Créer le type de paiement Abonnement Bus
    type_paiement, created = TypePaiement.objects.get_or_create(
        nom="Abonnement Bus",
        defaults={
            'description': "Paiement pour l'abonnement au transport scolaire",
            'actif': True
        }
    )
    
    if created:
        print(f"✓ Type de paiement '{type_paiement.nom}' créé avec succès")
    else:
        print(f"ℹ Type de paiement '{type_paiement.nom}' existe déjà")
    
    # Vérifier que les modes de paiement de base existent
    modes_base = [
        ("Espèces", "Paiement en espèces"),
        ("Mobile Money", "Paiement par Mobile Money (Orange Money, MTN, etc.)"),
        ("Chèque", "Paiement par chèque bancaire"),
        ("Virement", "Virement bancaire")
    ]
    
    print("\n=== Vérification des modes de paiement ===")
    for nom, description in modes_base:
        mode, created = ModePaiement.objects.get_or_create(
            nom=nom,
            defaults={
                'description': description,
                'frais_supplementaires': 0,
                'actif': True
            }
        )
        
        if created:
            print(f"✓ Mode de paiement '{mode.nom}' créé")
        else:
            print(f"ℹ Mode de paiement '{mode.nom}' existe déjà")
    
    print("\n=== Résumé ===")
    print(f"Types de paiement actifs: {TypePaiement.objects.filter(actif=True).count()}")
    print(f"Modes de paiement actifs: {ModePaiement.objects.filter(actif=True).count()}")
    
    # Lister tous les types de paiement
    print("\nTypes de paiement disponibles:")
    for tp in TypePaiement.objects.filter(actif=True).order_by('nom'):
        print(f"  - {tp.nom}")
    
    return type_paiement

if __name__ == '__main__':
    try:
        type_paiement = create_bus_payment_type()
        print(f"\n✅ Script terminé avec succès!")
        print(f"Le type de paiement 'Abonnement Bus' est maintenant disponible dans le système.")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de l'exécution: {e}")
        sys.exit(1)
