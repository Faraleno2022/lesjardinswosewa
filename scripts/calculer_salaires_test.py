#!/usr/bin/env python
"""
Script pour calculer et créer des états de salaire de test
"""

import os
import sys
import django
from datetime import datetime, date
from decimal import Decimal

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from salaires.models import Enseignant, PeriodeSalaire, EtatSalaire, AffectationClasse
from eleves.models import Ecole

def calculer_salaire_enseignant(enseignant, periode):
    """
    Calcule le salaire d'un enseignant pour une période donnée
    """
    print(f"Calcul du salaire pour {enseignant.nom} {enseignant.prenoms} - {periode}")
    
    # Salaire de base selon le type d'enseignant
    if enseignant.type_enseignant in ['GARDERIE', 'MATERNELLE', 'PRIMAIRE', 'ADMINISTRATEUR']:
        # Salaire fixe mensuel
        salaire_base = enseignant.salaire_fixe or Decimal('0')
        heures_travaillees = Decimal('0')  # Non applicable pour salaire fixe
        
    elif enseignant.type_enseignant == 'SECONDAIRE':
        # Calcul basé sur le taux horaire
        taux_horaire = enseignant.taux_horaire or Decimal('0')
        
        # Calcul des heures totales basé sur les affectations
        affectations = AffectationClasse.objects.filter(
            enseignant=enseignant,
            date_fin__isnull=True  # Affectations actives
        )
        
        heures_par_semaine = sum(aff.heures_par_semaine for aff in affectations)
        heures_travaillees = Decimal(str(heures_par_semaine)) * Decimal(str(periode.nombre_semaines))
        salaire_base = taux_horaire * heures_travaillees
        
    else:
        salaire_base = Decimal('0')
        heures_travaillees = Decimal('0')
    
    # Calcul des primes et déductions (exemple)
    prime_anciennete = Decimal('0')
    if enseignant.date_embauche:
        anciennete_annees = (date.today() - enseignant.date_embauche).days / 365
        if anciennete_annees >= 2:
            prime_anciennete = salaire_base * Decimal('0.05')  # 5% après 2 ans
        if anciennete_annees >= 5:
            prime_anciennete = salaire_base * Decimal('0.10')  # 10% après 5 ans
    
    prime_responsabilite = Decimal('0')
    if enseignant.type_enseignant == 'ADMINISTRATEUR':
        prime_responsabilite = Decimal('50000')  # Prime fixe pour admin
    
    # Déductions
    cotisation_sociale = salaire_base * Decimal('0.03')  # 3% de cotisation
    avance_sur_salaire = Decimal('0')  # À implémenter selon les besoins
    
    # Calculs finaux
    total_primes = prime_anciennete + prime_responsabilite
    total_deductions = cotisation_sociale + avance_sur_salaire
    salaire_brut = salaire_base + total_primes
    salaire_net = salaire_brut - total_deductions
    
    return {
        'salaire_base': salaire_base,
        'heures_travaillees': heures_travaillees,
        'prime_anciennete': prime_anciennete,
        'prime_responsabilite': prime_responsabilite,
        'total_primes': total_primes,
        'cotisation_sociale': cotisation_sociale,
        'avance_sur_salaire': avance_sur_salaire,
        'total_deductions': total_deductions,
        'salaire_brut': salaire_brut,
        'salaire_net': salaire_net,
    }

def creer_etats_salaire_periode(periode):
    """
    Crée les états de salaire pour tous les enseignants d'une période
    """
    print(f"\n=== Calcul des salaires pour {periode} ===")
    
    # Récupérer tous les enseignants actifs de l'école de la période
    enseignants = Enseignant.objects.filter(
        ecole=periode.ecole,
        statut='ACTIF'
    )
    
    etats_crees = 0
    
    for enseignant in enseignants:
        # Vérifier si un état existe déjà
        etat_existant = EtatSalaire.objects.filter(
            enseignant=enseignant,
            periode=periode
        ).first()
        
        if etat_existant:
            print(f"  État déjà existant pour {enseignant.nom} {enseignant.prenoms}")
            continue
        
        # Calculer le salaire
        calculs = calculer_salaire_enseignant(enseignant, periode)
        
        # Créer l'état de salaire
        etat = EtatSalaire.objects.create(
            enseignant=enseignant,
            periode=periode,
            total_heures=calculs['heures_travaillees'],
            salaire_base=calculs['salaire_base'],
            primes=calculs['total_primes'],
            deductions=calculs['total_deductions'],
            salaire_net=calculs['salaire_net'],
            valide=False,  # En attente de validation
            paye=False
        )
        
        print(f"  ✓ État créé pour {enseignant.nom} {enseignant.prenoms} - {calculs['salaire_net']:,.0f} GNF")
        etats_crees += 1
    
    print(f"\n{etats_crees} états de salaire créés pour {periode}")
    return etats_crees

def main():
    """
    Fonction principale pour calculer les salaires de test
    """
    print("=== CALCUL DES SALAIRES DE TEST ===\n")
    
    # Récupérer quelques périodes récentes pour chaque école
    ecoles = Ecole.objects.all()
    total_etats = 0
    
    for ecole in ecoles:
        print(f"\n--- École : {ecole.nom} ---")
        
        # Prendre les 3 dernières périodes ouvertes
        periodes = PeriodeSalaire.objects.filter(
            ecole=ecole,
            cloturee=False
        ).order_by('-annee', '-mois')[:3]
        
        if not periodes:
            print(f"Aucune période ouverte trouvée pour {ecole.nom}")
            continue
        
        for periode in periodes:
            etats_crees = creer_etats_salaire_periode(periode)
            total_etats += etats_crees
    
    print(f"\n=== RÉSUMÉ ===")
    print(f"Total des états de salaire créés : {total_etats}")
    
    # Statistiques finales
    total_etats_db = EtatSalaire.objects.count()
    etats_valides = EtatSalaire.objects.filter(valide=True).count()
    etats_payes = EtatSalaire.objects.filter(paye=True).count()
    
    print(f"États de salaire en base : {total_etats_db}")
    print(f"États validés : {etats_valides}")
    print(f"États payés : {etats_payes}")
    print(f"États en attente : {total_etats_db - etats_valides}")

if __name__ == '__main__':
    main()
