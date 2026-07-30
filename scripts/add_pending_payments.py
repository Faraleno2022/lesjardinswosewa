#!/usr/bin/env python
"""
Script pour ajouter des paiements en attente à valider
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement, TypePaiement, ModePaiement
from eleves.models import Eleve
from django.utils import timezone
from decimal import Decimal
from datetime import date

def add_pending_payments():
    """Ajouter plusieurs paiements en attente pour tester la validation"""
    
    print("💳 AJOUT DE PAIEMENTS EN ATTENTE")
    print("=" * 50)
    
    # Récupérer des élèves, types et modes de paiement
    eleves = list(Eleve.objects.all()[:4])
    types = list(TypePaiement.objects.all()[:3])
    modes = list(ModePaiement.objects.all()[:2])
    
    print(f"📊 Données disponibles:")
    print(f"   - Élèves: {len(eleves)}")
    print(f"   - Types de paiement: {len(types)}")
    print(f"   - Modes de paiement: {len(modes)}")
    
    if not eleves or not types or not modes:
        print("❌ Données insuffisantes pour créer des paiements")
        return
    
    # Données des paiements à créer
    paiements_data = [
        {
            'numero_recu': 'REC20250006',
            'montant': Decimal('75000'),
            'type_idx': 0,  # Premier type
            'mode_idx': 0,  # Premier mode
            'eleve_idx': 1  # Deuxième élève
        },
        {
            'numero_recu': 'REC20250007',
            'montant': Decimal('100000'),
            'type_idx': 1,  # Deuxième type
            'mode_idx': 1,  # Deuxième mode
            'eleve_idx': 2  # Troisième élève
        },
        {
            'numero_recu': 'REC20250008',
            'montant': Decimal('125000'),
            'type_idx': 0,  # Premier type
            'mode_idx': 0,  # Premier mode
            'eleve_idx': 3  # Quatrième élève
        }
    ]
    
    paiements_crees = []
    
    for data in paiements_data:
        try:
            # Vérifier si le paiement existe déjà
            if Paiement.objects.filter(numero_recu=data['numero_recu']).exists():
                print(f"⚠️  Paiement {data['numero_recu']} existe déjà, ignoré")
                continue
            
            # Créer le paiement
            paiement = Paiement.objects.create(
                eleve=eleves[data['eleve_idx']],
                type_paiement=types[data['type_idx']],
                mode_paiement=modes[data['mode_idx']],
                numero_recu=data['numero_recu'],
                montant=data['montant'],
                date_paiement=date.today(),
                statut='EN_ATTENTE'
            )
            
            paiements_crees.append(paiement)
            
            print(f"✅ Paiement créé:")
            print(f"   - Reçu: {paiement.numero_recu}")
            print(f"   - Élève: {paiement.eleve.nom_complet}")
            print(f"   - École: {paiement.eleve.classe.ecole.nom}")
            print(f"   - Montant: {paiement.montant:,} GNF")
            print(f"   - Type: {paiement.type_paiement.nom}")
            print(f"   - Mode: {paiement.mode_paiement.nom}")
            print(f"   - Statut: {paiement.statut}")
            print()
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du paiement {data['numero_recu']}: {e}")
    
    # Statistiques finales
    total_en_attente = Paiement.objects.filter(statut='EN_ATTENTE').count()
    
    print(f"📊 RÉSUMÉ:")
    print(f"   - Paiements créés: {len(paiements_crees)}")
    print(f"   - Total EN_ATTENTE: {total_en_attente}")
    
    if paiements_crees:
        print(f"\n🎯 POUR TESTER LA VALIDATION:")
        print(f"   1. Aller sur: http://127.0.0.1:8000/paiements/liste/?statut=EN_ATTENTE")
        print(f"   2. Vous devriez voir {total_en_attente} paiement(s) en attente")
        print(f"   3. Cliquer sur le bouton vert 'Valider' pour chaque paiement")
        print(f"   4. Le statut passera de 'En attente' → 'Validé'")

if __name__ == '__main__':
    add_pending_payments()
