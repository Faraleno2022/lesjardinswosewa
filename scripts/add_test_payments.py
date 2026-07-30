#!/usr/bin/env python
"""
Script pour ajouter des paiements de test
"""

import os
import sys
import django
from datetime import datetime, timedelta
from random import choice, randint

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Eleve
from paiements.models import Paiement, EcheancierPaiement, TypePaiement, ModePaiement
from decimal import Decimal

def add_test_payments():
    """Ajoute des paiements de test pour démonstration"""
    
    print("💳 Ajout de paiements de test...")
    print("=" * 50)
    
    # Récupérer les types et modes de paiement
    type_inscription = TypePaiement.objects.filter(nom__icontains='inscription').first()
    type_scolarite = TypePaiement.objects.filter(nom__icontains='scolarité').first()
    
    if not type_inscription:
        print("❌ Type de paiement 'Frais d'inscription' non trouvé")
        return
    
    if not type_scolarite:
        # Créer le type scolarité s'il n'existe pas
        type_scolarite = TypePaiement.objects.create(
            nom="Frais de scolarité",
            description="Paiement des frais de scolarité par tranches"
        )
        print("✅ Type de paiement 'Frais de scolarité' créé")
    
    # Modes de paiement
    mode_especes = ModePaiement.objects.filter(nom__icontains='espèces').first()
    mode_mobile = ModePaiement.objects.filter(nom__icontains='mobile').first()
    mode_virement = ModePaiement.objects.filter(nom__icontains='virement').first()
    
    modes_disponibles = [m for m in [mode_especes, mode_mobile, mode_virement] if m]
    
    if not modes_disponibles:
        print("❌ Aucun mode de paiement trouvé")
        return
    
    # Récupérer les élèves avec échéanciers
    eleves_avec_echeancier = []
    for eleve in Eleve.objects.filter(statut='ACTIF')[:10]:  # Limiter à 10 élèves
        if hasattr(eleve, 'echeancier'):
            eleves_avec_echeancier.append(eleve)
    
    if not eleves_avec_echeancier:
        print("❌ Aucun élève avec échéancier trouvé")
        return
    
    print(f"👥 {len(eleves_avec_echeancier)} élève(s) avec échéancier trouvé(s)")
    
    paiements_crees = 0
    
    # Ajouter des paiements pour chaque élève
    for eleve in eleves_avec_echeancier:
        print(f"\n🧑‍🎓 {eleve.nom_complet} ({eleve.classe.ecole.nom})")
        
        echeancier = eleve.echeancier
        
        # Probabilité de paiement (70% chance de payer les frais d'inscription)
        if randint(1, 100) <= 70 and echeancier.frais_inscription_du > 0:
            # Paiement des frais d'inscription (complet ou partiel)
            montant_inscription = echeancier.frais_inscription_du
            
            if randint(1, 100) <= 80:  # 80% paient complètement
                montant_paye = montant_inscription
                print(f"   💰 Frais d'inscription: {montant_paye:,.0f} GNF (complet)")
            else:  # 20% paient partiellement
                montant_paye = montant_inscription // 2
                print(f"   💰 Frais d'inscription: {montant_paye:,.0f} GNF (partiel)")
            
            # Créer le paiement
            paiement_inscription = Paiement.objects.create(
                eleve=eleve,
                type_paiement=type_inscription,
                mode_paiement=choice(modes_disponibles),
                montant=montant_paye,
                date_paiement=datetime.now().date() - timedelta(days=randint(1, 30)),
                statut='VALIDE',
                observations=f"Paiement frais d'inscription - {eleve.classe.ecole.nom}",
                numero_recu=f"REC-{datetime.now().strftime('%Y%m%d')}-{randint(1000, 9999)}"
            )
            
            # Mettre à jour l'échéancier
            echeancier.frais_inscription_paye += montant_paye
            echeancier.save()
            
            paiements_crees += 1
        
        # Probabilité de paiement de la 1ère tranche (50%)
        if randint(1, 100) <= 50 and echeancier.tranche_1_due > 0:
            montant_tranche = echeancier.tranche_1_due
            
            if randint(1, 100) <= 60:  # 60% paient complètement
                montant_paye = montant_tranche
                print(f"   📚 1ère tranche: {montant_paye:,.0f} GNF (complet)")
            else:  # 40% paient partiellement
                montant_paye = montant_tranche // 2
                print(f"   📚 1ère tranche: {montant_paye:,.0f} GNF (partiel)")
            
            paiement_tranche = Paiement.objects.create(
                eleve=eleve,
                type_paiement=type_scolarite,
                mode_paiement=choice(modes_disponibles),
                montant=montant_paye,
                date_paiement=datetime.now().date() - timedelta(days=randint(1, 20)),
                statut='VALIDE',
                observations=f"Paiement 1ère tranche - {eleve.classe}",
                numero_recu=f"REC-{datetime.now().strftime('%Y%m%d')}-{randint(1000, 9999)}"
            )
            
            # Mettre à jour l'échéancier
            echeancier.tranche_1_payee += montant_paye
            echeancier.save()
            
            paiements_crees += 1
        
        # Probabilité de paiement de la 2ème tranche (25%)
        if randint(1, 100) <= 25 and echeancier.tranche_2_due > 0:
            montant_tranche = echeancier.tranche_2_due
            montant_paye = montant_tranche // 2  # Toujours partiel pour la 2ème tranche
            
            print(f"   📚 2ème tranche: {montant_paye:,.0f} GNF (partiel)")
            
            paiement_tranche2 = Paiement.objects.create(
                eleve=eleve,
                type_paiement=type_scolarite,
                mode_paiement=choice(modes_disponibles),
                montant=montant_paye,
                date_paiement=datetime.now().date() - timedelta(days=randint(1, 10)),
                statut='VALIDE',
                observations=f"Paiement 2ème tranche - {eleve.classe}",
                numero_recu=f"REC-{datetime.now().strftime('%Y%m%d')}-{randint(1000, 9999)}"
            )
            
            # Mettre à jour l'échéancier
            echeancier.tranche_2_payee += montant_paye
            echeancier.save()
            
            paiements_crees += 1
    
    print(f"\n✅ {paiements_crees} paiement(s) créé(s) avec succès!")
    
    # Statistiques finales
    print(f"\n📊 Statistiques des paiements:")
    print("-" * 40)
    
    total_paiements = Paiement.objects.count()
    total_montant = sum(p.montant for p in Paiement.objects.all())
    
    print(f"💳 Total paiements: {total_paiements}")
    print(f"💰 Montant total: {total_montant:,.0f} GNF")
    
    # Par type de paiement
    for type_paiement in TypePaiement.objects.all():
        paiements_type = Paiement.objects.filter(type_paiement=type_paiement)
        if paiements_type.exists():
            nb_paiements = paiements_type.count()
            montant_type = sum(p.montant for p in paiements_type)
            print(f"   📋 {type_paiement.nom}: {nb_paiements} paiement(s), {montant_type:,.0f} GNF")
    
    # Par mode de paiement
    print(f"\n💳 Répartition par mode:")
    for mode_paiement in ModePaiement.objects.all():
        paiements_mode = Paiement.objects.filter(mode_paiement=mode_paiement)
        if paiements_mode.exists():
            nb_paiements = paiements_mode.count()
            montant_mode = sum(p.montant for p in paiements_mode)
            print(f"   💰 {mode_paiement.nom}: {nb_paiements} paiement(s), {montant_mode:,.0f} GNF")

if __name__ == '__main__':
    add_test_payments()
