from django.db import transaction
from .models import Classe, GrilleTarifaire
from datetime import date

def creer_classes_et_grilles_par_defaut(ecole, annee_scolaire=None):
    """
    Crée automatiquement les classes et grilles tarifaires par défaut pour une nouvelle école.
    
    Args:
        ecole: Instance de l'école
        annee_scolaire: Année scolaire (ex: "2025-2026"), par défaut année courante
    """
    if not annee_scolaire:
        today = date.today()
        if today.month >= 9:  # Septembre à décembre = nouvelle année scolaire
            annee_scolaire = f"{today.year}-{today.year+1}"
        else:  # Janvier à août = année scolaire en cours
            annee_scolaire = f"{today.year-1}-{today.year}"
    
    # Configuration par défaut des classes et tarifs (en GNF)
    classes_config = [
        # Maternelle/Garderie
        {"nom": "Garderie", "niveau": "GARDERIE", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 300000},
        
        # Primaire
        {"nom": "1ère Année", "niveau": "PRIMAIRE_1", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 400000},
        {"nom": "2ème Année", "niveau": "PRIMAIRE_2", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 400000},
        {"nom": "3ème Année", "niveau": "PRIMAIRE_3", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 450000},
        {"nom": "4ème Année", "niveau": "PRIMAIRE_4", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 450000},
        {"nom": "5ème Année", "niveau": "PRIMAIRE_5", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 500000},
        {"nom": "6ème Année", "niveau": "PRIMAIRE_6", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 500000},
        
        # Collège
        {"nom": "7ème", "niveau": "COLLEGE_7", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 600000},
        {"nom": "8ème", "niveau": "COLLEGE_8", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 600000},
        {"nom": "9ème", "niveau": "COLLEGE_9", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 650000},
        {"nom": "10ème année", "niveau": "COLLEGE_10", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 650000},
        
        # Lycée
        {"nom": "11ème Série Littéraire", "niveau": "LYCEE_11", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 700000},
        {"nom": "11ème Série Scientifique I", "niveau": "LYCEE_11", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 750000},
        {"nom": "11ème Série Scientifique II", "niveau": "LYCEE_11", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 750000},
        {"nom": "12ème SE", "niveau": "LYCEE_12", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 800000},
        {"nom": "12ème SM", "niveau": "LYCEE_12", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 800000},
        {"nom": "12ème SS", "niveau": "LYCEE_12", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 800000},
        
        # Terminale
        {"nom": "Terminale SE", "niveau": "TERMINALE", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 850000},
        {"nom": "Terminale SM", "niveau": "TERMINALE", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 850000},
        {"nom": "Terminale SS", "niveau": "TERMINALE", "frais_inscription": 30000, "frais_reinscription": 20000, "scolarite_annuelle": 850000},
    ]
    
    classes_creees = []
    grilles_creees = []
    
    with transaction.atomic():
        for config in classes_config:
            # Créer la classe
            classe, created = Classe.objects.get_or_create(
                ecole=ecole,
                nom=config["nom"],
                annee_scolaire=annee_scolaire,
                defaults={
                    'niveau': config["niveau"],
                    'capacite_max': 30,  # Capacité par défaut
                    'description': f"Classe {config['nom']} - {annee_scolaire}"
                }
            )
            
            if created:
                classes_creees.append(classe)
            
            # Créer la grille tarifaire correspondante
            grille, created = GrilleTarifaire.objects.get_or_create(
                ecole=ecole,
                niveau=config["niveau"],
                annee_scolaire=annee_scolaire,
                defaults={
                    'frais_inscription': config["frais_inscription"],
                    'frais_reinscription': config["frais_reinscription"],
                    'scolarite_annuelle': config["scolarite_annuelle"],
                    # Répartition par défaut en 3 tranches égales
                    'tranche_1': config["scolarite_annuelle"] // 3,
                    'tranche_2': config["scolarite_annuelle"] // 3,
                    'tranche_3': config["scolarite_annuelle"] - (2 * (config["scolarite_annuelle"] // 3)),
                    'date_limite_tranche_1': date(int(annee_scolaire.split('-')[0]), 10, 31),  # 31 octobre
                    'date_limite_tranche_2': date(int(annee_scolaire.split('-')[0]), 12, 31),  # 31 décembre
                    'date_limite_tranche_3': date(int(annee_scolaire.split('-')[1]), 3, 31),   # 31 mars
                }
            )
            
            if created:
                grilles_creees.append(grille)
    
    return {
        'classes_creees': classes_creees,
        'grilles_creees': grilles_creees,
        'total_classes': len(classes_creees),
        'total_grilles': len(grilles_creees)
    }


def valider_compte_utilisateur(user, ecole=None, telephone='', adresse=''):
    """
    Valide un compte utilisateur en attente et l'associe à son école.
    
    Args:
        user: Instance User à valider
        ecole: École à associer au profil (optionnel si déjà définie)
        telephone: Numéro de téléphone
        adresse: Adresse (optionnel)
    """
    from utilisateurs.models import Profil
    
    with transaction.atomic():
        # Activer le compte utilisateur
        user.is_active = True
        user.save()
        
        # Mettre à jour ou créer le profil
        profil, created = Profil.objects.get_or_create(
            user=user,
            defaults={
                'role': 'DIRECTEUR',
                'telephone': telephone,
                'adresse': adresse,
                'ecole': ecole,
                'is_validated': True,
                'actif': True,
                # Permissions par défaut pour un directeur
                'peut_valider_paiements': True,
                'peut_valider_depenses': True,
                'peut_generer_rapports': True,
                'peut_gerer_utilisateurs': True,
                'peut_ajouter_paiements': True,
                'peut_ajouter_depenses': True,
                'peut_ajouter_enseignants': True,
                'peut_modifier_paiements': True,
                'peut_modifier_depenses': True,
                'peut_consulter_rapports': True,
            }
        )
        
        if not created:
            # Mettre à jour le profil existant
            profil.is_validated = True
            profil.actif = True
            if telephone:
                profil.telephone = telephone
            if adresse:
                profil.adresse = adresse
            if ecole:
                profil.ecole = ecole
            profil.save()
    
    return profil
