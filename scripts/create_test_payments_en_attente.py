#!/usr/bin/env python
"""
Script pour créer des paiements en attente pour tester les totaux dynamiques
"""

import os
import sys
import django
from datetime import datetime, date

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from paiements.models import Paiement, TypePaiement, ModePaiement
from eleves.models import Eleve
from django.contrib.auth.models import User

def create_test_payments():
    """Créer des paiements en attente pour tester les totaux dynamiques"""
    
    print("🔄 CRÉATION DE PAIEMENTS EN ATTENTE POUR TEST")
    print("=" * 55)
    
    # Récupérer les données nécessaires
    eleves = Eleve.objects.filter(statut='ACTIF')[:4]  # 4 élèves
    type_scolarite = TypePaiement.objects.filter(nom__icontains='scolarité').first()
    type_inscription = TypePaiement.objects.filter(nom__icontains='inscription').first()
    mode_especes = ModePaiement.objects.filter(nom__icontains='espèces').first()
    mode_virement = ModePaiement.objects.filter(nom__icontains='virement').first()
    
    if not eleves.exists():
        print("❌ Aucun élève trouvé pour créer les paiements")
        return
    
    if not type_scolarite or not mode_especes:
        print("❌ Types ou modes de paiement manquants")
        return
    
    # Créer des paiements en attente
    paiements_test = [
        {
            'eleve': eleves[0],
            'type_paiement': type_scolarite,
            'mode_paiement': mode_especes,
            'montant': 150000,
            'date_paiement': date.today(),
            'observations': 'Paiement test - Scolarité 2ème tranche',
        },
        {
            'eleve': eleves[1],
            'type_paiement': type_inscription,
            'mode_paiement': mode_virement if mode_virement else mode_especes,
            'montant': 50000,
            'date_paiement': date.today(),
            'observations': 'Paiement test - Frais d\'inscription',
        },
        {
            'eleve': eleves[2],
            'type_paiement': type_scolarite,
            'mode_paiement': mode_especes,
            'montant': 200000,
            'date_paiement': date.today(),
            'observations': 'Paiement test - Scolarité 3ème tranche',
        },
        {
            'eleve': eleves[3] if len(eleves) > 3 else eleves[0],
            'type_paiement': type_scolarite,
            'mode_paiement': mode_especes,
            'montant': 100000,
            'date_paiement': date.today(),
            'observations': 'Paiement test - Rattrapage scolarité',
        },
    ]
    
    paiements_crees = 0
    montant_total_test = 0
    
    for paiement_data in paiements_test:
        try:
            paiement = Paiement.objects.create(
                eleve=paiement_data['eleve'],
                type_paiement=paiement_data['type_paiement'],
                mode_paiement=paiement_data['mode_paiement'],
                montant=paiement_data['montant'],
                date_paiement=paiement_data['date_paiement'],
                observations=paiement_data['observations'],
                statut='EN_ATTENTE'  # Important : statut EN_ATTENTE
            )
            
            print(f"✅ Paiement créé: {paiement.eleve.nom} {paiement.eleve.prenom}")
            print(f"   - Montant: {paiement.montant:,} GNF".replace(',', ' '))
            print(f"   - Type: {paiement.type_paiement.nom}")
            print(f"   - École: {paiement.eleve.classe.ecole.nom}")
            print(f"   - Statut: {paiement.statut}")
            print()
            
            paiements_crees += 1
            montant_total_test += paiement.montant
            
        except Exception as e:
            print(f"❌ Erreur lors de la création du paiement pour {paiement_data['eleve'].nom}: {e}")
    
    print(f"📊 RÉSUMÉ DES PAIEMENTS CRÉÉS:")
    print(f"   - Nombre de paiements: {paiements_crees}")
    print(f"   - Montant total: {montant_total_test:,} GNF".replace(',', ' '))
    print(f"   - Statut: EN_ATTENTE")
    print(f"   - Date: {date.today()}")
    
    # Vérification des totaux après création
    print(f"\n🔍 VÉRIFICATION DES TOTAUX APRÈS CRÉATION:")
    
    from django.db.models import Sum, Count
    
    # Totaux généraux
    total_paiements = Paiement.objects.count()
    montant_total = Paiement.objects.aggregate(total=Sum('montant'))['total'] or 0
    
    # Totaux en attente
    total_en_attente = Paiement.objects.filter(statut='EN_ATTENTE').count()
    montant_en_attente = Paiement.objects.filter(statut='EN_ATTENTE').aggregate(total=Sum('montant'))['total'] or 0
    
    # Totaux ce mois
    current_month = datetime.now().month
    current_year = datetime.now().year
    total_ce_mois = Paiement.objects.filter(
        date_paiement__month=current_month,
        date_paiement__year=current_year
    ).count()
    montant_ce_mois = Paiement.objects.filter(
        date_paiement__month=current_month,
        date_paiement__year=current_year
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    print(f"   - Total paiements: {total_paiements:,}".replace(',', ' '))
    print(f"   - Montant total: {montant_total:,} GNF".replace(',', ' '))
    print(f"   - En attente: {total_en_attente:,} paiements".replace(',', ' '))
    print(f"   - Montant en attente: {montant_en_attente:,} GNF".replace(',', ' '))
    print(f"   - Ce mois: {total_ce_mois:,} paiements".replace(',', ' '))
    print(f"   - Montant ce mois: {montant_ce_mois:,} GNF".replace(',', ' '))
    
    print(f"\n🎯 TEST VISUEL RECOMMANDÉ:")
    print(f"   1. Allez sur: http://127.0.0.1:8000/paiements/liste/")
    print(f"   2. Vérifiez les totaux en haut de la page:")
    print(f"      - Total paiements: {total_paiements:,}".replace(',', ' '))
    print(f"      - Montant total: {montant_total:,} GNF".replace(',', ' '))
    print(f"      - En attente: {total_en_attente:,} ({montant_en_attente:,} GNF)".replace(',', ' '))
    print(f"      - Ce mois: {total_ce_mois:,} ({montant_ce_mois:,} GNF)".replace(',', ' '))
    print(f"   3. Testez les filtres:")
    print(f"      - Filtre 'Statut: EN_ATTENTE' → devrait montrer {total_en_attente:,} paiements".replace(',', ' '))
    print(f"      - Filtre 'Statut: VALIDE' → devrait montrer les paiements validés")
    print(f"      - Filtre par école → totaux adaptés par école")
    print(f"   4. Validez quelques paiements et vérifiez que les totaux changent")
    
    print(f"\n✅ PAIEMENTS EN ATTENTE CRÉÉS AVEC SUCCÈS!")
    print(f"   Les totaux dynamiques sont maintenant testables visuellement.")

if __name__ == '__main__':
    create_test_payments()
