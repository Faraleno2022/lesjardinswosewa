#!/usr/bin/env python
"""
Script pour mettre à jour l'année scolaire de 2024-2025 vers 2025-2026
"""

import os
import sys
import django

# Configuration Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
django.setup()

from eleves.models import Classe, GrilleTarifaire
from paiements.models import EcheancierPaiement

def update_annee_scolaire():
    """Met à jour l'année scolaire de 2024-2025 vers 2025-2026"""
    
    print("📅 Mise à jour de l'année scolaire 2024-2025 → 2025-2026...")
    print("=" * 60)
    
    ancienne_annee = "2024-2025"
    nouvelle_annee = "2025-2026"
    
    # 1. Mise à jour des classes
    print("🏫 Mise à jour des classes...")
    classes_mises_a_jour = Classe.objects.filter(annee_scolaire=ancienne_annee).update(
        annee_scolaire=nouvelle_annee
    )
    print(f"   ✅ {classes_mises_a_jour} classe(s) mise(s) à jour")
    
    # 2. Mise à jour des grilles tarifaires
    print("\n💰 Mise à jour des grilles tarifaires...")
    grilles_mises_a_jour = GrilleTarifaire.objects.filter(annee_scolaire=ancienne_annee).update(
        annee_scolaire=nouvelle_annee
    )
    print(f"   ✅ {grilles_mises_a_jour} grille(s) tarifaire(s) mise(s) à jour")
    
    # 3. Mise à jour des échéanciers
    print("\n📋 Mise à jour des échéanciers...")
    echeanciers_mis_a_jour = EcheancierPaiement.objects.filter(annee_scolaire=ancienne_annee).update(
        annee_scolaire=nouvelle_annee
    )
    print(f"   ✅ {echeanciers_mis_a_jour} échéancier(s) mis à jour")
    
    # 4. Vérification finale
    print(f"\n📊 Vérification finale pour l'année {nouvelle_annee}:")
    print("-" * 50)
    
    # Compter les éléments par école
    from eleves.models import Ecole
    
    for ecole in Ecole.objects.all():
        classes_count = Classe.objects.filter(
            ecole=ecole, 
            annee_scolaire=nouvelle_annee
        ).count()
        
        grilles_count = GrilleTarifaire.objects.filter(
            ecole=ecole, 
            annee_scolaire=nouvelle_annee
        ).count()
        
        eleves_count = 0
        for classe in Classe.objects.filter(ecole=ecole, annee_scolaire=nouvelle_annee):
            eleves_count += classe.eleves.count()
        
        echeanciers_count = EcheancierPaiement.objects.filter(
            annee_scolaire=nouvelle_annee,
            eleve__classe__ecole=ecole
        ).count()
        
        print(f"🏫 {ecole.nom}:")
        print(f"   📚 Classes: {classes_count}")
        print(f"   💰 Grilles tarifaires: {grilles_count}")
        print(f"   🧑‍🎓 Élèves: {eleves_count}")
        print(f"   📋 Échéanciers: {echeanciers_count}")
        print()
    
    # 5. Statistiques globales
    total_classes = Classe.objects.filter(annee_scolaire=nouvelle_annee).count()
    total_grilles = GrilleTarifaire.objects.filter(annee_scolaire=nouvelle_annee).count()
    total_echeanciers = EcheancierPaiement.objects.filter(annee_scolaire=nouvelle_annee).count()
    
    print("📈 Statistiques globales:")
    print(f"   📚 Total classes {nouvelle_annee}: {total_classes}")
    print(f"   💰 Total grilles tarifaires {nouvelle_annee}: {total_grilles}")
    print(f"   📋 Total échéanciers {nouvelle_annee}: {total_echeanciers}")
    
    # Vérifier qu'il ne reste plus d'anciens éléments
    anciennes_classes = Classe.objects.filter(annee_scolaire=ancienne_annee).count()
    anciennes_grilles = GrilleTarifaire.objects.filter(annee_scolaire=ancienne_annee).count()
    anciens_echeanciers = EcheancierPaiement.objects.filter(annee_scolaire=ancienne_annee).count()
    
    if anciennes_classes == 0 and anciennes_grilles == 0 and anciens_echeanciers == 0:
        print(f"\n✅ Migration complète ! Plus aucun élément en {ancienne_annee}")
    else:
        print(f"\n⚠️  Éléments restants en {ancienne_annee}:")
        if anciennes_classes > 0:
            print(f"   📚 Classes: {anciennes_classes}")
        if anciennes_grilles > 0:
            print(f"   💰 Grilles: {anciennes_grilles}")
        if anciens_echeanciers > 0:
            print(f"   📋 Échéanciers: {anciens_echeanciers}")
    
    print(f"\n🎉 Mise à jour terminée avec succès !")
    print(f"📅 Nouvelle année scolaire active: {nouvelle_annee}")

if __name__ == '__main__':
    update_annee_scolaire()
