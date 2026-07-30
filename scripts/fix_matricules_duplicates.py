#!/usr/bin/env python3
"""
Script pour corriger les matricules vides ou dupliqués dans la base de données.
Utilise la codification officielle: GA, MPS, MMS, MGS, PN1-6, CN7-10, L11SL, L11SSI, L11SSII, L12SS/SM/SE, TSS/TSM/TSE

Usage:
    python manage.py shell < scripts/fix_matricules_duplicates.py
    ou
    python scripts/fix_matricules_duplicates.py
"""

import os
import sys
import django

# Configuration Django
if __name__ == '__main__':
    # Ajouter le répertoire parent au path pour les imports
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
    django.setup()

from django.db import transaction
from eleves.models import Eleve, _code_classe_from_nom_ou_niveau
from collections import defaultdict
import re

def fix_matricules():
    """Corrige les matricules vides ou dupliqués"""
    print("🔧 Début de la correction des matricules...")
    
    # Statistiques
    stats = {
        'vides_corriges': 0,
        'duplicates_corriges': 0,
        'erreurs': 0,
        'total_eleves': 0
    }
    
    with transaction.atomic():
        # 1. Traiter les matricules vides
        print("\n📋 Étape 1: Correction des matricules vides")
        eleves_vides = Eleve.objects.filter(matricule__isnull=True) | Eleve.objects.filter(matricule='')
        stats['total_eleves'] = Eleve.objects.count()
        
        for eleve in eleves_vides:
            try:
                # Générer un nouveau matricule basé sur la classe
                code = _code_classe_from_nom_ou_niveau(eleve.classe)
                if not code:
                    # Fallback de sécurité
                    code = f"CL{eleve.classe.id}"
                    print(f"⚠️  Fallback utilisé pour {eleve.nom_complet}: {code}")
                
                # Trouver le prochain numéro disponible
                base_prefix = f"{code}-"
                derniers = Eleve.objects.filter(matricule__startswith=base_prefix).order_by('-matricule')
                next_num = 1
                
                if derniers.exists():
                    dernier = derniers.first().matricule
                    m = re.search(r"^(?:" + re.escape(code) + r")-(\d+)$", dernier)
                    if m:
                        try:
                            next_num = int(m.group(1)) + 1
                        except:
                            next_num = 1
                
                # Générer matricule unique
                for tentative in range(10):  # Max 10 tentatives
                    candidat = f"{code}-{next_num:03d}"
                    if not Eleve.objects.filter(matricule=candidat).exists():
                        eleve.matricule = candidat
                        eleve.save()
                        print(f"✅ {eleve.nom_complet}: {candidat}")
                        stats['vides_corriges'] += 1
                        break
                    next_num += 1
                else:
                    print(f"❌ Impossible de générer un matricule unique pour {eleve.nom_complet}")
                    stats['erreurs'] += 1
                    
            except Exception as e:
                print(f"❌ Erreur pour {eleve.nom_complet}: {e}")
                stats['erreurs'] += 1
        
        # 2. Traiter les matricules dupliqués
        print("\n📋 Étape 2: Correction des matricules dupliqués")
        
        # Grouper par matricule pour trouver les doublons
        matricules_count = defaultdict(list)
        for eleve in Eleve.objects.all():
            if eleve.matricule:  # Ignorer les vides (déjà traités)
                matricules_count[eleve.matricule].append(eleve)
        
        # Traiter les doublons
        for matricule, eleves_list in matricules_count.items():
            if len(eleves_list) > 1:
                print(f"\n🔍 Doublon détecté: {matricule} ({len(eleves_list)} élèves)")
                
                # Garder le premier (plus ancien par ID), renommer les autres
                eleves_list.sort(key=lambda x: x.id)
                premier = eleves_list[0]
                print(f"   ✅ Conservé: {premier.nom_complet} (ID: {premier.id})")
                
                for eleve in eleves_list[1:]:
                    try:
                        # Générer nouveau matricule pour les doublons
                        code = _code_classe_from_nom_ou_niveau(eleve.classe)
                        if not code:
                            code = f"CL{eleve.classe.id}"
                        
                        # Trouver le prochain numéro disponible
                        base_prefix = f"{code}-"
                        derniers = Eleve.objects.filter(matricule__startswith=base_prefix).order_by('-matricule')
                        next_num = 1
                        
                        if derniers.exists():
                            dernier = derniers.first().matricule
                            m = re.search(r"^(?:" + re.escape(code) + r")-(\d+)$", dernier)
                            if m:
                                try:
                                    next_num = int(m.group(1)) + 1
                                except:
                                    next_num = 1
                        
                        # Générer matricule unique
                        for tentative in range(10):
                            candidat = f"{code}-{next_num:03d}"
                            if not Eleve.objects.filter(matricule=candidat).exists():
                                ancien_matricule = eleve.matricule
                                eleve.matricule = candidat
                                eleve.save()
                                print(f"   🔄 {eleve.nom_complet}: {ancien_matricule} → {candidat}")
                                stats['duplicates_corriges'] += 1
                                break
                            next_num += 1
                        else:
                            print(f"   ❌ Impossible de générer un matricule unique pour {eleve.nom_complet}")
                            stats['erreurs'] += 1
                            
                    except Exception as e:
                        print(f"   ❌ Erreur pour {eleve.nom_complet}: {e}")
                        stats['erreurs'] += 1
    
    # 3. Rapport final
    print("\n" + "="*60)
    print("📊 RAPPORT FINAL")
    print("="*60)
    print(f"Total élèves dans la base: {stats['total_eleves']}")
    print(f"Matricules vides corrigés: {stats['vides_corriges']}")
    print(f"Matricules dupliqués corrigés: {stats['duplicates_corriges']}")
    print(f"Erreurs rencontrées: {stats['erreurs']}")
    print(f"Total corrections: {stats['vides_corriges'] + stats['duplicates_corriges']}")
    
    if stats['erreurs'] == 0:
        print("\n✅ Toutes les corrections ont été appliquées avec succès!")
    else:
        print(f"\n⚠️  {stats['erreurs']} erreur(s) rencontrée(s). Vérifiez les logs ci-dessus.")
    
    return stats

def verify_matricules():
    """Vérifie l'état des matricules après correction"""
    print("\n🔍 Vérification post-correction...")
    
    # Vérifier les vides
    vides = Eleve.objects.filter(matricule__isnull=True) | Eleve.objects.filter(matricule='')
    print(f"Matricules vides restants: {vides.count()}")
    
    # Vérifier les doublons
    from django.db.models import Count
    doublons = (Eleve.objects.values('matricule')
                .annotate(count=Count('matricule'))
                .filter(count__gt=1))
    print(f"Matricules dupliqués restants: {doublons.count()}")
    
    if doublons.exists():
        print("Doublons détectés:")
        for d in doublons:
            print(f"  - {d['matricule']}: {d['count']} occurrences")
    
    # Statistiques par code
    print("\n📈 Répartition par code de classe:")
    codes_stats = defaultdict(int)
    for eleve in Eleve.objects.all():
        if eleve.matricule:
            code = eleve.matricule.split('-')[0] if '-' in eleve.matricule else 'AUTRE'
            codes_stats[code] += 1
    
    for code, count in sorted(codes_stats.items()):
        print(f"  {code}: {count} élèves")

if __name__ == '__main__':
    print("🎯 Script de correction des matricules")
    print("Codification: GA, MPS/MMS/MGS, PN1-6, CN7-10, L11SL/SSI/SSII, L12SS/SM/SE, TSS/TSM/TSE")
    
    # Demander confirmation
    response = input("\nVoulez-vous procéder à la correction? (oui/non): ").lower()
    if response in ['oui', 'o', 'yes', 'y']:
        stats = fix_matricules()
        verify_matricules()
        print("\n🎉 Script terminé!")
    else:
        print("❌ Opération annulée.")
