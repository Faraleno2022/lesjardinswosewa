#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script d'initialisation des données de test pour le module Salaires
Crée des enseignants, affectations de classes, périodes de salaire et états de salaire
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

from django.contrib.auth.models import User
from eleves.models import Ecole, Classe
from salaires.models import Enseignant, AffectationClasse, PeriodeSalaire, EtatSalaire, DetailHeuresClasse

def creer_enseignants():
    """Crée des enseignants de test pour chaque école et type"""
    print("🧑‍🏫 Création des enseignants...")
    
    # Récupérer les écoles
    ecoles = Ecole.objects.all()
    if not ecoles.exists():
        print("❌ Aucune école trouvée. Veuillez d'abord initialiser les données de base.")
        return
    
    # Créer un utilisateur admin pour valider les salaires
    admin_user, created = User.objects.get_or_create(
        username='admin_salaires',
        defaults={
            'first_name': 'Admin',
            'last_name': 'Salaires',
            'email': 'admin.salaires@ecole.gn',
            'is_staff': True
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print(f"✅ Utilisateur admin créé: {admin_user.username}")
    
    enseignants_data = [
        # École Sonfonia
        {
            'nom': 'DIALLO',
            'prenoms': 'Mamadou Alpha',
            'telephone': '+224 622 11 11 11',
            'email': 'mamadou.diallo@sonfonia.gn',
            'adresse': 'Sonfonia Centre, Conakry',
            'type_enseignant': 'garderie',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('800000'),
            'ecole': 'myschool - Sonfonia'
        },
        {
            'nom': 'BARRY',
            'prenoms': 'Aissatou',
            'telephone': '+224 622 22 22 22',
            'email': 'aissatou.barry@sonfonia.gn',
            'adresse': 'Sonfonia T3, Conakry',
            'type_enseignant': 'maternelle',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('900000'),
            'ecole': 'myschool - Sonfonia'
        },
        {
            'nom': 'CAMARA',
            'prenoms': 'Ibrahima',
            'telephone': '+224 622 33 33 33',
            'email': 'ibrahima.camara@sonfonia.gn',
            'adresse': 'Sonfonia Gare, Conakry',
            'type_enseignant': 'primaire',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('1200000'),
            'ecole': 'myschool - Sonfonia'
        },
        {
            'nom': 'TOURE',
            'prenoms': 'Fatoumata',
            'telephone': '+224 622 44 44 44',
            'email': 'fatoumata.toure@sonfonia.gn',
            'adresse': 'Sonfonia Port, Conakry',
            'type_enseignant': 'secondaire',
            'mode_salaire': 'horaire',
            'taux_horaire': Decimal('15000'),
            'ecole': 'myschool - Sonfonia'
        },
        {
            'nom': 'CONDE',
            'prenoms': 'Mohamed Lamine',
            'telephone': '+224 622 55 55 55',
            'email': 'mohamed.conde@sonfonia.gn',
            'adresse': 'Sonfonia Mosquée, Conakry',
            'type_enseignant': 'administrateur',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('1500000'),
            'ecole': 'myschool - Sonfonia'
        },
        
        # École Somayah
        {
            'nom': 'SYLLA',
            'prenoms': 'Mariama',
            'telephone': '+224 655 11 11 11',
            'email': 'mariama.sylla@somayah.gn',
            'adresse': 'Matam Centre, Conakry',
            'type_enseignant': 'garderie',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('750000'),
            'ecole': 'myschool - Somayah'
        },
        {
            'nom': 'KABA',
            'prenoms': 'Alseny',
            'telephone': '+224 655 22 22 22',
            'email': 'alseny.kaba@somayah.gn',
            'adresse': 'Matam Lido, Conakry',
            'type_enseignant': 'maternelle',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('850000'),
            'ecole': 'myschool - Somayah'
        },
        {
            'nom': 'SOUMAH',
            'prenoms': 'Hadja Aminata',
            'telephone': '+224 655 33 33 33',
            'email': 'aminata.soumah@somayah.gn',
            'adresse': 'Matam Mosquée, Conakry',
            'type_enseignant': 'primaire',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('1100000'),
            'ecole': 'myschool - Somayah'
        },
        {
            'nom': 'BANGOURA',
            'prenoms': 'Sekou Oumar',
            'telephone': '+224 655 44 44 44',
            'email': 'sekou.bangoura@somayah.gn',
            'adresse': 'Matam Marché, Conakry',
            'type_enseignant': 'secondaire',
            'mode_salaire': 'horaire',
            'taux_horaire': Decimal('12000'),
            'ecole': 'myschool - Somayah'
        },
        {
            'nom': 'KEITA',
            'prenoms': 'Mory',
            'telephone': '+224 655 55 55 55',
            'email': 'mory.keita@somayah.gn',
            'adresse': 'Matam Autoroute, Conakry',
            'type_enseignant': 'administrateur',
            'mode_salaire': 'fixe',
            'salaire_fixe': Decimal('1400000'),
            'ecole': 'myschool - Somayah'
        }
    ]
    
    enseignants_crees = 0
    
    for data in enseignants_data:
        try:
            ecole = Ecole.objects.get(nom=data['ecole'])
            
            # Vérifier si l'enseignant existe déjà
            if Enseignant.objects.filter(nom=data['nom'], prenoms=data['prenoms'], ecole=ecole).exists():
                print(f"⚠️  Enseignant {data['prenoms']} {data['nom']} existe déjà pour {ecole.nom}")
                continue
            
            enseignant_data = {
                'nom': data['nom'],
                'prenoms': data['prenoms'],
                'telephone': data['telephone'],
                'email': data['email'],
                'adresse': data['adresse'],
                'type_enseignant': data['type_enseignant'].upper(),
                'ecole': ecole,
                'statut': 'ACTIF',
                'date_embauche': date(2024, 9, 1)
            }
            
            if data['type_enseignant'] != 'secondaire':
                enseignant_data['salaire_fixe'] = data['salaire_fixe']
            else:
                enseignant_data['taux_horaire'] = data['taux_horaire']
            
            enseignant = Enseignant.objects.create(**enseignant_data)
            enseignants_crees += 1
            print(f"✅ Enseignant créé: {enseignant.nom_complet} ({enseignant.get_type_enseignant_display()}) - {ecole.nom}")
            
        except Ecole.DoesNotExist:
            print(f"❌ École '{data['ecole']}' non trouvée")
        except Exception as e:
            print(f"❌ Erreur lors de la création de {data['prenoms']} {data['nom']}: {e}")
    
    print(f"📊 Total enseignants créés: {enseignants_crees}")

def creer_affectations_classes():
    """Crée les affectations des enseignants aux classes"""
    print("\n📚 Création des affectations de classes...")
    
    # Récupérer tous les enseignants et classes
    enseignants = Enseignant.objects.all()
    classes = Classe.objects.all()
    
    if not enseignants.exists() or not classes.exists():
        print("❌ Aucun enseignant ou classe trouvé")
        return
    
    affectations_data = [
        # Sonfonia
        {'enseignant': 'DIALLO Mamadou Alpha', 'classe': 'Petite Section', 'heures_semaine': 30},
        {'enseignant': 'BARRY Aissatou', 'classe': 'Moyenne Section', 'heures_semaine': 30},
        {'enseignant': 'BARRY Aissatou', 'classe': 'Grande Section', 'heures_semaine': 25},
        {'enseignant': 'CAMARA Ibrahima', 'classe': 'CP1', 'heures_semaine': 30},
        {'enseignant': 'CAMARA Ibrahima', 'classe': 'CP2', 'heures_semaine': 25},
        {'enseignant': 'TOURE Fatoumata', 'classe': '7ème', 'heures_semaine': 20},
        {'enseignant': 'TOURE Fatoumata', 'classe': '8ème', 'heures_semaine': 18},
        
        # Somayah
        {'enseignant': 'SYLLA Mariama', 'classe': 'Petite Section', 'heures_semaine': 32},
        {'enseignant': 'KABA Alseny', 'classe': 'Moyenne Section', 'heures_semaine': 30},
        {'enseignant': 'KABA Alseny', 'classe': 'Grande Section', 'heures_semaine': 28},
        {'enseignant': 'SOUMAH Hadja Aminata', 'classe': 'CP1', 'heures_semaine': 30},
        {'enseignant': 'SOUMAH Hadja Aminata', 'classe': 'CP2', 'heures_semaine': 25},
        {'enseignant': 'BANGOURA Sekou Oumar', 'classe': '7ème', 'heures_semaine': 22},
        {'enseignant': 'BANGOURA Sekou Oumar', 'classe': '8ème', 'heures_semaine': 20},
    ]
    
    affectations_creees = 0
    
    for data in affectations_data:
        try:
            # Trouver l'enseignant
            nom_complet = data['enseignant'].split()
            nom = nom_complet[0]
            prenoms = ' '.join(nom_complet[1:])
            
            enseignant = Enseignant.objects.get(nom=nom, prenoms=prenoms)
            
            # Trouver la classe dans la même école
            classe = Classe.objects.get(nom=data['classe'], ecole=enseignant.ecole)
            
            # Vérifier si l'affectation existe déjà
            if AffectationClasse.objects.filter(enseignant=enseignant, classe=classe).exists():
                print(f"⚠️  Affectation existe déjà: {enseignant.nom_complet} -> {classe.nom}")
                continue
            
            affectation = AffectationClasse.objects.create(
                enseignant=enseignant,
                classe=classe,
                heures_par_semaine=data['heures_semaine'],
                date_debut=date(2025, 10, 1),  # Début année scolaire
                actif=True
            )
            
            affectations_creees += 1
            print(f"✅ Affectation créée: {enseignant.nom_complet} -> {classe.nom} ({data['heures_semaine']}h/semaine)")
            
        except (Enseignant.DoesNotExist, Classe.DoesNotExist) as e:
            print(f"❌ Erreur affectation {data['enseignant']} -> {data['classe']}: {e}")
        except Exception as e:
            print(f"❌ Erreur lors de la création de l'affectation: {e}")
    
    print(f"📊 Total affectations créées: {affectations_creees}")

def creer_periodes_salaire():
    """Crée les périodes de salaire pour chaque école"""
    print("\n📅 Création des périodes de salaire...")
    
    ecoles = Ecole.objects.all()
    periodes_creees = 0
    
    # Périodes pour l'année scolaire 2025-2026
    periodes_data = [
        {'mois': 'Octobre', 'annee': 2025, 'debut': date(2025, 10, 1), 'fin': date(2025, 10, 31), 'semaines': 4},
        {'mois': 'Novembre', 'annee': 2025, 'debut': date(2025, 11, 1), 'fin': date(2025, 11, 30), 'semaines': 4},
        {'mois': 'Décembre', 'annee': 2025, 'debut': date(2025, 12, 1), 'fin': date(2025, 12, 31), 'semaines': 4},
        {'mois': 'Janvier', 'annee': 2026, 'debut': date(2026, 1, 1), 'fin': date(2026, 1, 31), 'semaines': 4},
        {'mois': 'Février', 'annee': 2026, 'debut': date(2026, 2, 1), 'fin': date(2026, 2, 28), 'semaines': 4},
        {'mois': 'Mars', 'annee': 2026, 'debut': date(2026, 3, 1), 'fin': date(2026, 3, 31), 'semaines': 4},
        {'mois': 'Avril', 'annee': 2026, 'debut': date(2026, 4, 1), 'fin': date(2026, 4, 30), 'semaines': 4},
        {'mois': 'Mai', 'annee': 2026, 'debut': date(2026, 5, 1), 'fin': date(2026, 5, 31), 'semaines': 4},
        {'mois': 'Juin', 'annee': 2026, 'debut': date(2026, 6, 1), 'fin': date(2026, 6, 30), 'semaines': 4},
    ]
    
    for ecole in ecoles:
        for data in periodes_data:
            try:
                nom_periode = f"{data['mois']} {data['annee']}"
                
                # Vérifier si la période existe déjà
                if PeriodeSalaire.objects.filter(mois=data['debut'].month, annee=data['annee'], ecole=ecole).exists():
                    print(f"⚠️  Période existe déjà: {nom_periode} - {ecole.nom}")
                    continue
                
                periode = PeriodeSalaire.objects.create(
                    mois=data['debut'].month,
                    annee=data['annee'],
                    ecole=ecole,
                    nombre_semaines=data['semaines'],
                    cloturee=data['mois'] in ['Octobre', 'Novembre']  # Les 2 premiers mois sont clôturés
                )
                
                periodes_creees += 1
                print(f"✅ Période créée: {nom_periode} - {ecole.nom}")
                
            except Exception as e:
                print(f"❌ Erreur lors de la création de la période {nom_periode}: {e}")
    
    print(f"📊 Total périodes créées: {periodes_creees}")

def creer_etats_salaire():
    """Crée quelques états de salaire de test"""
    print("\n💰 Création des états de salaire...")
    
    # Récupérer les périodes clôturées
    periodes_cloturees = PeriodeSalaire.objects.filter(cloturee=True)
    enseignants = Enseignant.objects.filter(statut='ACTIF')
    admin_user = User.objects.get(username='admin_salaires')
    
    etats_crees = 0
    
    for periode in periodes_cloturees:
        # Créer des états pour les enseignants de cette école
        enseignants_ecole = enseignants.filter(ecole=periode.ecole)
        
        for enseignant in enseignants_ecole:
            try:
                # Vérifier si l'état existe déjà
                if EtatSalaire.objects.filter(enseignant=enseignant, periode=periode).exists():
                    print(f"⚠️  État existe déjà: {enseignant.nom_complet} - {periode.nom_periode}")
                    continue
                
                # Calculer le salaire
                if enseignant.type_enseignant != 'SECONDAIRE':
                    salaire_base = enseignant.salaire_fixe or Decimal('0')
                    total_heures = 0
                else:
                    # Pour les enseignants à taux horaire, calculer selon les affectations
                    affectations = AffectationClasse.objects.filter(enseignant=enseignant, actif=True)
                    total_heures = sum(aff.heures_par_semaine for aff in affectations) * periode.nombre_semaines
                    salaire_base = (enseignant.taux_horaire or Decimal('0')) * total_heures
                
                # Ajouter quelques primes et déductions aléatoires
                import random
                prime_transport = Decimal(str(random.randint(50000, 100000)))
                prime_performance = Decimal(str(random.randint(0, 200000)))
                deduction_absence = Decimal(str(random.randint(0, 50000)))
                
                salaire_brut = salaire_base + prime_transport + prime_performance
                total_deductions = deduction_absence
                salaire_net = salaire_brut - total_deductions
                
                etat = EtatSalaire.objects.create(
                    enseignant=enseignant,
                    periode=periode,
                    salaire_base=salaire_base,
                    prime_transport=prime_transport,
                    prime_performance=prime_performance,
                    deduction_absence=deduction_absence,
                    salaire_brut=salaire_brut,
                    total_deductions=total_deductions,
                    salaire_net=salaire_net,
                    total_heures=total_heures,
                    valide=True,
                    valide_par=admin_user,
                    date_validation=datetime.now(),
                    paye=periode.nom_periode == 'Octobre 2025'  # Premier mois payé
                )
                
                # Créer les détails par classe pour les enseignants à taux horaire
                if enseignant.type_enseignant == 'SECONDAIRE':
                    affectations = AffectationClasse.objects.filter(enseignant=enseignant, actif=True)
                    for affectation in affectations:
                        heures_periode = affectation.heures_par_semaine * periode.nombre_semaines
                        montant_classe = (enseignant.taux_horaire or Decimal('0')) * heures_periode
                        
                        DetailHeuresClasse.objects.create(
                            etat_salaire=etat,
                            classe=affectation.classe,
                            heures_prevues=heures_periode,
                            heures_effectuees=heures_periode,
                            taux_horaire=enseignant.taux_horaire or Decimal('0'),
                            montant=montant_classe
                        )
                
                etats_crees += 1
                print(f"✅ État créé: {enseignant.nom_complet} - {periode.nom_periode} ({salaire_net:,.0f} GNF)")
                
            except Exception as e:
                print(f"❌ Erreur lors de la création de l'état pour {enseignant.nom_complet}: {e}")
    
    print(f"📊 Total états de salaire créés: {etats_crees}")

def afficher_statistiques():
    """Affiche les statistiques finales"""
    print("\n" + "="*60)
    print("📊 STATISTIQUES FINALES")
    print("="*60)
    
    # Statistiques générales
    total_enseignants = Enseignant.objects.count()
    enseignants_actifs = Enseignant.objects.filter(statut='ACTIF').count()
    total_affectations = AffectationClasse.objects.count()
    total_periodes = PeriodeSalaire.objects.count()
    total_etats = EtatSalaire.objects.count()
    
    print(f"👥 Enseignants: {total_enseignants} (dont {enseignants_actifs} actifs)")
    print(f"📚 Affectations de classes: {total_affectations}")
    print(f"📅 Périodes de salaire: {total_periodes}")
    print(f"💰 États de salaire: {total_etats}")
    
    # Statistiques par école
    print("\n📍 Répartition par école:")
    for ecole in Ecole.objects.all():
        nb_enseignants = Enseignant.objects.filter(ecole=ecole).count()
        nb_periodes = PeriodeSalaire.objects.filter(ecole=ecole).count()
        nb_etats = EtatSalaire.objects.filter(enseignant__ecole=ecole).count()
        print(f"  • {ecole.nom}: {nb_enseignants} enseignants, {nb_periodes} périodes, {nb_etats} états")
    
    # Statistiques par type d'enseignant
    print("\n👨‍🏫 Répartition par type:")
    types = ['garderie', 'maternelle', 'primaire', 'secondaire', 'administrateur']
    for type_ens in types:
        nb = Enseignant.objects.filter(type_enseignant=type_ens).count()
        if nb > 0:
            print(f"  • {type_ens.title()}: {nb} enseignants")
    
    # Statistiques par mode de salaire
    print("\n💵 Répartition par mode de salaire:")
    nb_fixe = Enseignant.objects.exclude(type_enseignant='SECONDAIRE').count()
    nb_horaire = Enseignant.objects.filter(type_enseignant='SECONDAIRE').count()
    print(f"  • Salaire fixe: {nb_fixe} enseignants")
    print(f"  • Taux horaire: {nb_horaire} enseignants")
    
    # États de salaire par statut
    if total_etats > 0:
        print("\n📋 États de salaire:")
        nb_valides = EtatSalaire.objects.filter(valide=True).count()
        nb_payes = EtatSalaire.objects.filter(paye=True).count()
        print(f"  • Validés: {nb_valides}/{total_etats}")
        print(f"  • Payés: {nb_payes}/{total_etats}")
        
        # Montant total des salaires
        from django.db.models import Sum
        total_salaires = EtatSalaire.objects.aggregate(total=Sum('salaire_net'))['total'] or 0
        print(f"  • Montant total: {total_salaires:,.0f} GNF")

def main():
    """Fonction principale"""
    print("🚀 INITIALISATION DES DONNÉES DU MODULE SALAIRES")
    print("="*60)
    
    try:
        creer_enseignants()
        creer_affectations_classes()
        creer_periodes_salaire()
        creer_etats_salaire()
        afficher_statistiques()
        
        print("\n✅ Initialisation terminée avec succès!")
        print("🌐 Vous pouvez maintenant accéder au module Salaires via l'interface web.")
        
    except Exception as e:
        print(f"\n❌ Erreur lors de l'initialisation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
