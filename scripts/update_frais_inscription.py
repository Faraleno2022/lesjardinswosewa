#!/usr/bin/env python
"""
Script pour mettre à jour les frais d'inscription dans les grilles tarifaires
- École Somayah : 30 000 GNF
- École Sonfonia (myschool) : 50 000 GNF
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Ecole, GrilleTarifaire
from decimal import Decimal

def update_frais_inscription():
    """Met à jour les frais d'inscription pour chaque école"""
    
    print("🎓 Mise à jour des frais d'inscription...")
    print("=" * 50)
    
    # Définition des frais par école
    frais_par_ecole = {
        'Somayah': Decimal('30000'),
        'myschool': Decimal('50000')
    }
    
    # Mise à jour pour chaque école
    for nom_ecole, montant_frais in frais_par_ecole.items():
        try:
            # Recherche de l'école (recherche flexible)
            ecole = None
            ecoles = Ecole.objects.all()
            for e in ecoles:
                if nom_ecole.lower() in e.nom.lower() or e.nom.lower() in nom_ecole.lower():
                    ecole = e
                    break
            
            if not ecole:
                print(f"❌ École '{nom_ecole}' non trouvée")
                continue
            
            # Mise à jour de toutes les grilles tarifaires de cette école
            grilles = GrilleTarifaire.objects.filter(ecole=ecole)
            
            if not grilles.exists():
                print(f"⚠️  Aucune grille tarifaire trouvée pour {ecole.nom}")
                continue
            
            # Mise à jour
            nb_updated = grilles.update(frais_inscription=montant_frais)
            
            print(f"✅ {ecole.nom}:")
            print(f"   - Frais d'inscription: {montant_frais:,.0f} GNF")
            print(f"   - {nb_updated} grille(s) tarifaire(s) mise(s) à jour")
            print()
            
        except Exception as e:
            print(f"❌ Erreur pour l'école '{nom_ecole}': {e}")
            continue
    
    # Vérification finale
    print("📊 Vérification finale:")
    print("-" * 30)
    
    for ecole in Ecole.objects.all():
        grilles = ecole.grilles_tarifaires.all()
        if grilles.exists():
            frais_inscription = grilles.first().frais_inscription
            print(f"🏫 {ecole.nom}: {frais_inscription:,.0f} GNF")
        else:
            print(f"🏫 {ecole.nom}: Aucune grille tarifaire")
    
    print("\n✅ Mise à jour terminée avec succès!")

if __name__ == '__main__':
    update_frais_inscription()
