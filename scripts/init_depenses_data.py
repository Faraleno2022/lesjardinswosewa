#!/usr/bin/env python
"""
Script d'initialisation des données de test pour le module Dépenses
Crée des catégories, fournisseurs et dépenses de test
"""

import os
import sys
import django
from datetime import datetime, timedelta
from decimal import Decimal
import random

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from django.contrib.auth.models import User
from django.db import models
from depenses.models import (
    CategorieDepense, Fournisseur, Depense, 
    BudgetAnnuel, HistoriqueDepense
)

def create_categories():
    """Créer les catégories de dépenses"""
    print("🏷️  Création des catégories de dépenses...")
    
    categories_data = [
        {
            'nom': 'Fonctionnement',
            'code': 'FONC',
            'description': 'Dépenses de fonctionnement courant de l\'école'
        },
        {
            'nom': 'Investissement',
            'code': 'INV',
            'description': 'Investissements en équipements et infrastructure'
        },
        {
            'nom': 'Personnel',
            'code': 'PERS',
            'description': 'Salaires et charges du personnel'
        },
        {
            'nom': 'Maintenance',
            'code': 'MAINT',
            'description': 'Maintenance et réparations'
        },
        {
            'nom': 'Fournitures scolaires',
            'code': 'FOUR',
            'description': 'Fournitures et matériel pédagogique'
        },
        {
            'nom': 'Utilities',
            'code': 'UTIL',
            'description': 'Électricité, eau, internet, téléphone'
        },
        {
            'nom': 'Transport',
            'code': 'TRANS',
            'description': 'Frais de transport et carburant'
        },
        {
            'nom': 'Formation',
            'code': 'FORM',
            'description': 'Formation du personnel et développement'
        }
    ]
    
    categories_created = 0
    for cat_data in categories_data:
        try:
            # Vérifier d'abord si la catégorie existe par code ou nom
            categorie = CategorieDepense.objects.filter(
                models.Q(code=cat_data['code']) | models.Q(nom=cat_data['nom'])
            ).first()
            
            if categorie:
                # Mettre à jour si nécessaire
                if not categorie.actif:
                    categorie.actif = True
                    categorie.save()
                print(f"   ℹ️  Catégorie existante: {categorie.code} - {categorie.nom}")
            else:
                # Créer une nouvelle catégorie
                categorie = CategorieDepense.objects.create(
                    code=cat_data['code'],
                    nom=cat_data['nom'],
                    description=cat_data['description'],
                    actif=True
                )
                categories_created += 1
                print(f"   ✅ Catégorie créée: {categorie.code} - {categorie.nom}")
        except Exception as e:
            print(f"   ⚠️  Erreur avec catégorie {cat_data['code']}: {e}")
            continue
    
    print(f"📊 {categories_created} nouvelles catégories créées")
    return CategorieDepense.objects.filter(actif=True)

def create_fournisseurs():
    """Créer les fournisseurs"""
    print("\n🏢 Création des fournisseurs...")
    
    fournisseurs_data = [
        {
            'nom': 'Électricité de Guinée (EDG)',
            'type_fournisseur': 'ADMINISTRATION',
            'adresse': 'Conakry, Guinée',
            'telephone': '+224 622 123 456',
            'email': 'contact@edg.gn'
        },
        {
            'nom': 'Société des Eaux de Guinée (SEG)',
            'type_fournisseur': 'ADMINISTRATION',
            'adresse': 'Conakry, Guinée',
            'telephone': '+224 622 234 567',
            'email': 'contact@seg.gn'
        },
        {
            'nom': 'Orange Guinée',
            'type_fournisseur': 'ENTREPRISE',
            'adresse': 'Immeuble Kaloum Center, Conakry',
            'telephone': '+224 622 345 678',
            'email': 'entreprise@orange.gn'
        },
        {
            'nom': 'Papeterie Moderne SARL',
            'type_fournisseur': 'ENTREPRISE',
            'adresse': 'Marché Madina, Conakry',
            'telephone': '+224 622 456 789',
            'email': 'contact@papeterie-moderne.gn'
        },
        {
            'nom': 'Garage Auto Plus',
            'type_fournisseur': 'ENTREPRISE',
            'adresse': 'Route de Donka, Conakry',
            'telephone': '+224 622 567 890',
            'email': 'garage@autoplus.gn'
        },
        {
            'nom': 'Mamadou DIALLO - Électricien',
            'type_fournisseur': 'PARTICULIER',
            'adresse': 'Quartier Hamdallaye, Conakry',
            'telephone': '+224 622 678 901',
            'email': 'mamadou.diallo@gmail.com'
        },
        {
            'nom': 'Librairie Universitaire',
            'type_fournisseur': 'ENTREPRISE',
            'adresse': 'Avenue de la République, Conakry',
            'telephone': '+224 622 789 012',
            'email': 'contact@librairie-univ.gn'
        },
        {
            'nom': 'Société de Nettoyage PROPRE',
            'type_fournisseur': 'ENTREPRISE',
            'adresse': 'Cité Chemin de Fer, Conakry',
            'telephone': '+224 622 890 123',
            'email': 'contact@propre.gn'
        }
    ]
    
    fournisseurs_created = 0
    for four_data in fournisseurs_data:
        fournisseur, created = Fournisseur.objects.get_or_create(
            nom=four_data['nom'],
            defaults={
                'type_fournisseur': four_data['type_fournisseur'],
                'adresse': four_data['adresse'],
                'telephone': four_data['telephone'],
                'email': four_data['email'],
                'actif': True
            }
        )
        if created:
            fournisseurs_created += 1
            print(f"   ✅ Fournisseur créé: {fournisseur.nom}")
    
    print(f"🏢 {fournisseurs_created} nouveaux fournisseurs créés")
    return Fournisseur.objects.filter(actif=True)

def create_depenses(categories, fournisseurs, user):
    """Créer des dépenses de test"""
    print("\n💰 Création des dépenses de test...")
    
    # Données de dépenses réalistes pour une école
    depenses_data = [
        {
            'numero_facture': 'EDG-2025-001',
            'libelle': 'Facture électricité janvier 2025',
            'description': 'Consommation électrique du mois de janvier pour les deux sites',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('850000'),
            'taux_tva': Decimal('18'),
            'statut': 'PAYEE',
            'categorie_code': 'UTIL',
            'fournisseur_nom': 'Électricité de Guinée (EDG)',
            'days_ago': 25
        },
        {
            'numero_facture': 'SEG-2025-002',
            'libelle': 'Facture eau janvier 2025',
            'description': 'Consommation d\'eau potable pour les deux écoles',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('320000'),
            'taux_tva': Decimal('18'),
            'statut': 'PAYEE',
            'categorie_code': 'UTIL',
            'fournisseur_nom': 'Société des Eaux de Guinée (SEG)',
            'days_ago': 20
        },
        {
            'numero_facture': 'ORA-2025-003',
            'libelle': 'Abonnement internet et téléphone',
            'description': 'Forfait internet haut débit et communications téléphoniques',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('450000'),
            'taux_tva': Decimal('18'),
            'statut': 'VALIDEE',
            'categorie_code': 'UTIL',
            'fournisseur_nom': 'Orange Guinée',
            'days_ago': 15
        },
        {
            'numero_facture': 'PAP-2025-004',
            'libelle': 'Fournitures scolaires T2',
            'description': 'Cahiers, stylos, crayons, gommes pour le 2ème trimestre',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('1200000'),
            'taux_tva': Decimal('18'),
            'statut': 'EN_ATTENTE',
            'categorie_code': 'FOUR',
            'fournisseur_nom': 'Papeterie Moderne SARL',
            'days_ago': 10
        },
        {
            'numero_facture': 'GAR-2025-005',
            'libelle': 'Réparation bus scolaire',
            'description': 'Changement de pneus et révision générale du bus',
            'type_depense': 'MAINTENANCE',
            'montant_ht': Decimal('750000'),
            'taux_tva': Decimal('18'),
            'statut': 'VALIDEE',
            'categorie_code': 'MAINT',
            'fournisseur_nom': 'Garage Auto Plus',
            'days_ago': 8
        },
        {
            'numero_facture': 'ELEC-2025-006',
            'libelle': 'Installation éclairage LED',
            'description': 'Remplacement de l\'éclairage traditionnel par des LED dans 5 classes',
            'type_depense': 'INVESTISSEMENT',
            'montant_ht': Decimal('2500000'),
            'taux_tva': Decimal('18'),
            'statut': 'EN_ATTENTE',
            'categorie_code': 'INV',
            'fournisseur_nom': 'Mamadou DIALLO - Électricien',
            'days_ago': 5
        },
        {
            'numero_facture': 'LIB-2025-007',
            'libelle': 'Manuels scolaires 2025',
            'description': 'Commande de nouveaux manuels pour les classes de CP à CM2',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('1800000'),
            'taux_tva': Decimal('18'),
            'statut': 'BROUILLON',
            'categorie_code': 'FOUR',
            'fournisseur_nom': 'Librairie Universitaire',
            'days_ago': 3
        },
        {
            'numero_facture': 'NET-2025-008',
            'libelle': 'Service de nettoyage janvier',
            'description': 'Nettoyage quotidien des locaux et espaces communs',
            'type_depense': 'FONCTIONNEMENT',
            'montant_ht': Decimal('600000'),
            'taux_tva': Decimal('18'),
            'statut': 'PAYEE',
            'categorie_code': 'FONC',
            'fournisseur_nom': 'Société de Nettoyage PROPRE',
            'days_ago': 30
        }
    ]
    
    depenses_created = 0
    for dep_data in depenses_data:
        # Trouver la catégorie et le fournisseur
        try:
            categorie = categories.get(code=dep_data['categorie_code'])
            fournisseur = fournisseurs.get(nom=dep_data['fournisseur_nom'])
        except:
            print(f"   ⚠️  Catégorie ou fournisseur non trouvé pour {dep_data['numero_facture']}")
            continue
        
        # Calculer les dates
        date_facture = datetime.now().date() - timedelta(days=dep_data['days_ago'])
        date_echeance = date_facture + timedelta(days=30)  # Échéance à 30 jours
        
        # Calculer les montants
        montant_ht = dep_data['montant_ht']
        taux_tva = dep_data['taux_tva']
        montant_tva = montant_ht * taux_tva / 100
        montant_ttc = montant_ht + montant_tva
        
        # Créer la dépense
        depense, created = Depense.objects.get_or_create(
            numero_facture=dep_data['numero_facture'],
            defaults={
                'categorie': categorie,
                'fournisseur': fournisseur,
                'libelle': dep_data['libelle'],
                'description': dep_data['description'],
                'type_depense': dep_data['type_depense'],
                'montant_ht': montant_ht,
                'taux_tva': taux_tva,
                'montant_tva': montant_tva,
                'montant_ttc': montant_ttc,
                'date_facture': date_facture,
                'date_echeance': date_echeance,
                'statut': dep_data['statut'],
                'cree_par': user,
                'date_creation': datetime.now() - timedelta(days=dep_data['days_ago'])
            }
        )
        
        if created:
            depenses_created += 1
            print(f"   ✅ Dépense créée: {depense.numero_facture} - {depense.montant_ttc:,.0f} GNF")
            
            # Créer l'historique de création
            HistoriqueDepense.objects.create(
                depense=depense,
                action='CREATION',
                description=f'Dépense créée: {depense.libelle}',
                nouveau_statut=depense.statut,
                utilisateur=user,
                date_action=depense.date_creation
            )
            
            # Si la dépense est validée ou payée, ajouter l'historique correspondant
            if depense.statut in ['VALIDEE', 'PAYEE']:
                depense.valide_par = user
                depense.date_validation = depense.date_creation + timedelta(hours=2)
                depense.save()
                
                HistoriqueDepense.objects.create(
                    depense=depense,
                    action='VALIDATION',
                    description=f'Dépense validée: {depense.libelle}',
                    ancien_statut='EN_ATTENTE',
                    nouveau_statut='VALIDEE',
                    utilisateur=user,
                    date_action=depense.date_validation
                )
            
            if depense.statut == 'PAYEE':
                depense.date_paiement = date_facture + timedelta(days=random.randint(1, 25))
                depense.save()
                
                HistoriqueDepense.objects.create(
                    depense=depense,
                    action='PAIEMENT',
                    description=f'Dépense payée: {depense.libelle}',
                    ancien_statut='VALIDEE',
                    nouveau_statut='PAYEE',
                    utilisateur=user,
                    date_action=datetime.combine(depense.date_paiement, datetime.min.time())
                )
    
    print(f"💰 {depenses_created} nouvelles dépenses créées")

def create_budgets(categories, user):
    """Créer des budgets annuels"""
    print("\n📊 Création des budgets annuels 2025...")
    
    budgets_data = {
        'FONC': Decimal('15000000'),  # 15M GNF
        'INV': Decimal('8000000'),    # 8M GNF
        'PERS': Decimal('25000000'),  # 25M GNF
        'MAINT': Decimal('3000000'),  # 3M GNF
        'FOUR': Decimal('5000000'),   # 5M GNF
        'UTIL': Decimal('4000000'),   # 4M GNF
        'TRANS': Decimal('2000000'),  # 2M GNF
        'FORM': Decimal('1500000'),   # 1.5M GNF
    }
    
    budgets_created = 0
    for code, montant in budgets_data.items():
        try:
            categorie = categories.get(code=code)
            budget, created = BudgetAnnuel.objects.get_or_create(
                annee=2025,
                categorie=categorie,
                defaults={
                    'budget_prevu': montant,
                    'budget_engage': Decimal('0'),
                    'budget_consomme': Decimal('0'),
                    'cree_par': user
                }
            )
            if created:
                budgets_created += 1
                print(f"   ✅ Budget créé: {categorie.nom} - {montant:,.0f} GNF")
        except:
            print(f"   ⚠️  Catégorie {code} non trouvée pour le budget")
    
    print(f"📊 {budgets_created} nouveaux budgets créés")

def main():
    """Fonction principale"""
    print("🚀 INITIALISATION DES DONNÉES DU MODULE DÉPENSES")
    print("=" * 60)
    
    # Vérifier qu'un utilisateur existe
    try:
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.first()
        if not user:
            print("❌ Aucun utilisateur trouvé. Créez d'abord un utilisateur.")
            return
        print(f"👤 Utilisateur utilisé: {user.username}")
    except Exception as e:
        print(f"❌ Erreur lors de la récupération de l'utilisateur: {e}")
        return
    
    try:
        # Créer les données de base
        categories = create_categories()
        fournisseurs = create_fournisseurs()
        create_depenses(categories, fournisseurs, user)
        create_budgets(categories, user)
        
        print("\n" + "=" * 60)
        print("✅ INITIALISATION TERMINÉE AVEC SUCCÈS!")
        print("\n📊 RÉSUMÉ:")
        print(f"   • Catégories: {CategorieDepense.objects.count()}")
        print(f"   • Fournisseurs: {Fournisseur.objects.count()}")
        print(f"   • Dépenses: {Depense.objects.count()}")
        print(f"   • Budgets 2025: {BudgetAnnuel.objects.filter(annee=2025).count()}")
        
        # Statistiques des dépenses
        total_depenses = Depense.objects.count()
        montant_total = sum(d.montant_ttc for d in Depense.objects.all())
        print(f"\n💰 STATISTIQUES FINANCIÈRES:")
        print(f"   • Total dépenses: {total_depenses}")
        print(f"   • Montant total: {montant_total:,.0f} GNF")
        print(f"   • Dépenses payées: {Depense.objects.filter(statut='PAYEE').count()}")
        print(f"   • Dépenses en attente: {Depense.objects.filter(statut='EN_ATTENTE').count()}")
        
        print(f"\n🔗 Accédez au module: http://127.0.0.1:8000/depenses/")
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
