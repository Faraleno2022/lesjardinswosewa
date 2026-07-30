"""
Système de rappels de paiement automatique
Envoie des messages aux parents pour les paiements en retard
"""

from django.db import models
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal
from datetime import datetime, timedelta
import logging

from .models import EcheancierPaiement, Relance, ConfigurationPaiement
from eleves.models import Eleve

logger = logging.getLogger(__name__)

class GestionnaireRappels:
    """Gestionnaire principal pour les rappels de paiement"""
    
    def __init__(self):
        self.templates_messages = {
            'SMS': {
                'PREMIER_RAPPEL': """🏫 École Moderne
Cher(e) parent de {prenom} {nom},
Votre enfant a un solde impayé de {solde:,.0f} GNF.
Échéance dépassée: {date_echeance}
Merci de régulariser rapidement.
Contact: {telephone_ecole}""",
                
                'DEUXIEME_RAPPEL': """🏫 École Moderne - RAPPEL URGENT
Cher(e) parent de {prenom} {nom},
Solde impayé: {solde:,.0f} GNF
Échéance dépassée depuis {jours_retard} jours.
Merci de nous contacter rapidement.
Contact: {telephone_ecole}""",
                
                'DERNIER_RAPPEL': """🏫 École Moderne - DERNIER RAPPEL
Cher(e) parent de {prenom} {nom},
Solde impayé: {solde:,.0f} GNF
Retard: {jours_retard} jours
Risque de suspension des cours.
Contactez-nous IMMÉDIATEMENT.
Contact: {telephone_ecole}"""
            },
            
            'WHATSAPP': {
                'PREMIER_RAPPEL': """🏫 *École Moderne*

Bonjour,

Nous vous informons que votre enfant *{prenom} {nom}* ({classe}) a un solde impayé de *{solde:,.0f} GNF*.

📅 Échéance dépassée: {date_echeance}
💰 Montant dû: {solde:,.0f} GNF

Merci de régulariser ce paiement dans les plus brefs délais.

📞 Contact: {telephone_ecole}
🏫 Administration""",
                
                'DEUXIEME_RAPPEL': """🏫 *École Moderne - RAPPEL URGENT*

Bonjour,

⚠️ *RAPPEL URGENT* ⚠️

Votre enfant *{prenom} {nom}* ({classe}) a un solde impayé de *{solde:,.0f} GNF*.

📅 Échéance dépassée depuis: *{jours_retard} jours*
💰 Montant dû: *{solde:,.0f} GNF*

Merci de nous contacter rapidement pour régulariser cette situation.

📞 Contact: {telephone_ecole}
🏫 Administration""",
                
                'DERNIER_RAPPEL': """🏫 *École Moderne - DERNIER RAPPEL*

Bonjour,

🚨 *DERNIER RAPPEL* 🚨

Votre enfant *{prenom} {nom}* ({classe}) a un solde impayé de *{solde:,.0f} GNF*.

📅 Retard: *{jours_retard} jours*
⚠️ *Risque de suspension des cours*

Contactez-nous IMMÉDIATEMENT pour éviter toute interruption de la scolarité.

📞 Contact: {telephone_ecole}
🏫 Administration"""
            },
            
            'EMAIL': {
                'PREMIER_RAPPEL': """Rappel de paiement - {prenom} {nom}""",
                'DEUXIEME_RAPPEL': """URGENT - Rappel de paiement - {prenom} {nom}""",
                'DERNIER_RAPPEL': """DERNIER RAPPEL - Paiement en retard - {prenom} {nom}"""
            }
        }
    
    def detecter_eleves_en_retard(self, jours_grace=7):
        """
        Détecte les élèves en retard de paiement
        
        Args:
            jours_grace: Nombre de jours de grâce après l'échéance
        
        Returns:
            QuerySet des élèves en retard
        """
        aujourd_hui = timezone.now().date()
        date_limite = aujourd_hui - timedelta(days=jours_grace)
        
        # Récupérer les échéanciers avec des impayés
        echeanciers_retard = EcheancierPaiement.objects.filter(
            models.Q(
                date_echeance_inscription__lt=date_limite,
                frais_inscription_paye__lt=models.F('frais_inscription_du')
            ) |
            models.Q(
                date_echeance_tranche_1__lt=date_limite,
                tranche_1_payee__lt=models.F('tranche_1_due')
            ) |
            models.Q(
                date_echeance_tranche_2__lt=date_limite,
                tranche_2_payee__lt=models.F('tranche_2_due')
            ) |
            models.Q(
                date_echeance_tranche_3__lt=date_limite,
                tranche_3_payee__lt=models.F('tranche_3_due')
            )
        ).select_related('eleve', 'eleve__classe')
        
        return echeanciers_retard
    
    def calculer_niveau_rappel(self, eleve_id):
        """
        Calcule le niveau de rappel selon l'historique
        
        Returns:
            str: 'PREMIER_RAPPEL', 'DEUXIEME_RAPPEL', ou 'DERNIER_RAPPEL'
        """
        # Compter les rappels des 30 derniers jours
        date_limite = timezone.now() - timedelta(days=30)
        nb_rappels = Relance.objects.filter(
            eleve_id=eleve_id,
            date_creation__gte=date_limite,
            statut__in=['ENREGISTREE', 'ENVOYEE']
        ).count()
        
        if nb_rappels == 0:
            return 'PREMIER_RAPPEL'
        elif nb_rappels == 1:
            return 'DEUXIEME_RAPPEL'
        else:
            return 'DERNIER_RAPPEL'
    
    def calculer_jours_retard(self, echeancier):
        """Calcule le nombre de jours de retard maximum"""
        aujourd_hui = timezone.now().date()
        jours_retard = 0
        
        # Vérifier chaque échéance
        if (echeancier.frais_inscription_paye < echeancier.frais_inscription_du and 
            echeancier.date_echeance_inscription < aujourd_hui):
            jours_retard = max(jours_retard, (aujourd_hui - echeancier.date_echeance_inscription).days)
        
        if (echeancier.tranche_1_payee < echeancier.tranche_1_due and 
            echeancier.date_echeance_tranche_1 < aujourd_hui):
            jours_retard = max(jours_retard, (aujourd_hui - echeancier.date_echeance_tranche_1).days)
        
        if (echeancier.tranche_2_payee < echeancier.tranche_2_due and 
            echeancier.date_echeance_tranche_2 < aujourd_hui):
            jours_retard = max(jours_retard, (aujourd_hui - echeancier.date_echeance_tranche_2).days)
        
        if (echeancier.tranche_3_payee < echeancier.tranche_3_due and 
            echeancier.date_echeance_tranche_3 < aujourd_hui):
            jours_retard = max(jours_retard, (aujourd_hui - echeancier.date_echeance_tranche_3).days)
        
        return jours_retard
    
    def generer_message_rappel(self, eleve, echeancier, canal='SMS', niveau_rappel='PREMIER_RAPPEL'):
        """
        Génère le message de rappel personnalisé
        
        Args:
            eleve: Instance Eleve
            echeancier: Instance EcheancierPaiement
            canal: 'SMS', 'WHATSAPP', ou 'EMAIL'
            niveau_rappel: 'PREMIER_RAPPEL', 'DEUXIEME_RAPPEL', ou 'DERNIER_RAPPEL'
        
        Returns:
            str: Message formaté
        """
        # Calculer les données du message
        solde_restant = echeancier.solde_restant
        jours_retard = self.calculer_jours_retard(echeancier)
        
        # Trouver la date d'échéance la plus ancienne dépassée
        aujourd_hui = timezone.now().date()
        date_echeance = None
        
        if (echeancier.frais_inscription_paye < echeancier.frais_inscription_du and 
            echeancier.date_echeance_inscription < aujourd_hui):
            date_echeance = echeancier.date_echeance_inscription
        
        if (echeancier.tranche_1_payee < echeancier.tranche_1_due and 
            echeancier.date_echeance_tranche_1 < aujourd_hui):
            if not date_echeance or echeancier.date_echeance_tranche_1 < date_echeance:
                date_echeance = echeancier.date_echeance_tranche_1
        
        # Données pour le template
        context = {
            'prenom': eleve.prenom,
            'nom': eleve.nom,
            'classe': eleve.classe.nom if eleve.classe else 'N/A',
            'solde': solde_restant,
            'jours_retard': jours_retard,
            'date_echeance': date_echeance.strftime('%d/%m/%Y') if date_echeance else 'N/A',
            'telephone_ecole': getattr(eleve.classe.ecole, 'telephone', 'N/A') if eleve.classe and eleve.classe.ecole else 'N/A'
        }
        
        # Récupérer le template
        template = self.templates_messages.get(canal, {}).get(niveau_rappel, '')
        
        if template:
            return template.format(**context)
        else:
            return f"Rappel de paiement pour {eleve.prenom} {eleve.nom} - Solde: {solde_restant:,.0f} GNF"
    
    def creer_rappel(self, eleve, canal='SMS', message=None, utilisateur=None):
        """
        Crée un rappel dans la base de données
        
        Args:
            eleve: Instance Eleve
            canal: Canal de communication
            message: Message personnalisé (optionnel)
            utilisateur: Utilisateur qui crée le rappel
        
        Returns:
            Relance: Instance créée
        """
        try:
            echeancier = eleve.echeancier
        except EcheancierPaiement.DoesNotExist:
            logger.warning(f"Pas d'échéancier pour l'élève {eleve.id}")
            return None
        
        # Générer le message si non fourni
        if not message:
            niveau_rappel = self.calculer_niveau_rappel(eleve.id)
            message = self.generer_message_rappel(eleve, echeancier, canal, niveau_rappel)
        
        # Créer la relance
        relance = Relance.objects.create(
            eleve=eleve,
            canal=canal,
            message=message,
            solde_estime=echeancier.solde_restant,
            cree_par=utilisateur,
            statut='ENREGISTREE'
        )
        
        logger.info(f"Rappel créé pour {eleve.nom_complet} via {canal}")
        return relance
    
    def generer_rappels_automatiques(self, canal='SMS', utilisateur=None, limite=50):
        """
        Génère automatiquement les rappels pour tous les élèves en retard
        
        Args:
            canal: Canal de communication
            utilisateur: Utilisateur qui lance la génération
            limite: Nombre maximum de rappels à créer
        
        Returns:
            dict: Statistiques de génération
        """
        stats = {
            'total_eleves_retard': 0,
            'rappels_crees': 0,
            'erreurs': 0,
            'eleves_traites': []
        }
        
        # Détecter les élèves en retard
        echeanciers_retard = self.detecter_eleves_en_retard()
        stats['total_eleves_retard'] = echeanciers_retard.count()
        
        # Limiter le nombre de rappels
        echeanciers_retard = echeanciers_retard[:limite]
        
        for echeancier in echeanciers_retard:
            try:
                eleve = echeancier.eleve
                
                # Vérifier si un rappel récent existe déjà
                dernier_rappel = Relance.objects.filter(
                    eleve=eleve,
                    date_creation__gte=timezone.now() - timedelta(days=7)
                ).first()
                
                if dernier_rappel:
                    logger.info(f"Rappel récent existe pour {eleve.nom_complet}, ignoré")
                    continue
                
                # Créer le rappel
                relance = self.creer_rappel(eleve, canal, utilisateur=utilisateur)
                
                if relance:
                    stats['rappels_crees'] += 1
                    stats['eleves_traites'].append({
                        'eleve': eleve.nom_complet,
                        'solde': echeancier.solde_restant,
                        'canal': canal
                    })
                
            except Exception as e:
                logger.error(f"Erreur lors de la création du rappel pour {echeancier.eleve.nom_complet}: {e}")
                stats['erreurs'] += 1
        
        return stats
    
    def marquer_rappel_envoye(self, relance_id, succes=True, erreur=None):
        """
        Marque un rappel comme envoyé ou en échec
        
        Args:
            relance_id: ID de la relance
            succes: True si envoyé avec succès
            erreur: Message d'erreur si échec
        """
        try:
            relance = Relance.objects.get(id=relance_id)
            
            if succes:
                relance.statut = 'ENVOYEE'
                relance.date_envoi = timezone.now()
            else:
                relance.statut = 'ECHEC'
            
            relance.save()
            
            logger.info(f"Rappel {relance_id} marqué comme {'envoyé' if succes else 'en échec'}")
            
        except Relance.DoesNotExist:
            logger.error(f"Relance {relance_id} introuvable")
    
    def obtenir_statistiques_rappels(self, periode_jours=30):
        """
        Obtient les statistiques des rappels sur une période
        
        Args:
            periode_jours: Nombre de jours à analyser
        
        Returns:
            dict: Statistiques détaillées
        """
        date_debut = timezone.now() - timedelta(days=periode_jours)
        
        rappels = Relance.objects.filter(date_creation__gte=date_debut)
        
        stats = {
            'total_rappels': rappels.count(),
            'rappels_envoyes': rappels.filter(statut='ENVOYEE').count(),
            'rappels_echec': rappels.filter(statut='ECHEC').count(),
            'rappels_en_attente': rappels.filter(statut='ENREGISTREE').count(),
            'par_canal': {},
            'montant_total_impaye': Decimal('0'),
            'eleves_concernes': rappels.values('eleve').distinct().count()
        }
        
        # Statistiques par canal
        for canal, _ in Relance.CANAL_CHOICES:
            stats['par_canal'][canal] = rappels.filter(canal=canal).count()
        
        # Montant total des impayés
        stats['montant_total_impaye'] = sum(
            rappel.solde_estime for rappel in rappels if rappel.solde_estime
        )
        
        return stats

# Instance globale du gestionnaire
gestionnaire_rappels = GestionnaireRappels()
