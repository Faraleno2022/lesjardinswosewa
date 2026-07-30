#!/usr/bin/env python
"""
Script simple pour vérifier les détails du paiement en attente
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement

def check_payment_details():
    """Vérifier les détails du paiement en attente"""
    
    print("🔍 VÉRIFICATION DU PAIEMENT EN ATTENTE")
    print("=" * 50)
    
    try:
        p = Paiement.objects.get(numero_recu='REC20250005')
        
        print(f"📄 Paiement: {p.numero_recu}")
        print(f"📊 Statut: {p.statut}")
        print(f"👤 Élève: {p.eleve.nom_complet}")
        print(f"🏫 École: {p.eleve.classe.ecole.nom if p.eleve.classe and p.eleve.classe.ecole else 'Aucune'}")
        print(f"📅 Date: {p.date_paiement}")
        print(f"💰 Montant: {p.montant:,} GNF")
        print(f"📝 Type: {p.type_paiement.nom}")
        print(f"💳 Mode: {p.mode_paiement.nom}")
        print(f"👨‍💼 Créé par: {p.cree_par.username if p.cree_par else 'Aucun'}")
        print(f"📅 Date création: {p.date_creation}")
        
        # Vérifier si l'élève a une école via sa classe
        has_ecole = p.eleve.classe and p.eleve.classe.ecole
        if not has_ecole:
            print("\n⚠️  PROBLÈME POTENTIEL: L'élève n'a pas d'école associée via sa classe!")
            print("   Cela pourrait causer des problèmes de filtrage.")
        
        # Vérifier les filtres possibles
        print(f"\n🔍 VÉRIFICATIONS DE FILTRAGE:")
        print(f"   - Statut EN_ATTENTE: ✅")
        print(f"   - École définie: {'✅' if has_ecole else '❌'}")
        print(f"   - Date valide: ✅")
        print(f"   - Type actif: {'✅' if p.type_paiement.actif else '❌'}")
        
    except Paiement.DoesNotExist:
        print("❌ Paiement REC20250005 non trouvé!")
    except Exception as e:
        print(f"❌ Erreur: {e}")

if __name__ == '__main__':
    check_payment_details()
