"""
Module d'envoi d'abonnements bus et alertes d'expiration via WhatsApp
Génère un message avec les détails de l'abonnement et un lien vers le PDF du reçu
"""

import logging
import urllib.parse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.urls import reverse
from django.utils import timezone

from .models import AbonnementBus

logger = logging.getLogger(__name__)


class WhatsAppBusSender:
    """Classe pour gérer l'envoi d'infos bus via WhatsApp"""
    
    def _get_telephone_parent(self, eleve):
        """Récupère le numéro de téléphone du parent"""
        if eleve.responsable_principal and eleve.responsable_principal.telephone:
            return eleve.responsable_principal.telephone
        elif hasattr(eleve, 'responsable_secondaire') and eleve.responsable_secondaire and eleve.responsable_secondaire.telephone:
            return eleve.responsable_secondaire.telephone
        return None
    
    def _formater_numero_whatsapp(self, telephone):
        """Formate le numéro pour WhatsApp (format international)"""
        if not telephone:
            return None
        
        clean_number = telephone.replace(' ', '').replace('-', '').replace('.', '')
        
        if not clean_number.startswith('+'):
            if clean_number.startswith('00'):
                clean_number = '+' + clean_number[2:]
            elif clean_number.startswith('224'):
                clean_number = '+' + clean_number
            else:
                clean_number = '+224' + clean_number
        
        return clean_number
    
    def _generer_message_abonnement(self, abonnement, pdf_url=None):
        """Génère le message WhatsApp pour un abonnement bus (confirmation/reçu)"""
        eleve = abonnement.eleve
        ecole = eleve.classe.ecole if eleve.classe else None
        nom_ecole = ecole.nom if ecole else "École"
        tel_ecole = ecole.tous_telephones if ecole else ""
        email_ecole = ecole.email if ecole else ""
        
        # Formater le montant
        montant_formate = f"{abonnement.montant:,.0f}".replace(",", " ")
        
        message = f"""🚌 *{nom_ecole} - Abonnement Bus Scolaire*

Bonjour Cher Parent,

Nous confirmons l'abonnement au bus scolaire pour votre enfant *{eleve.prenom} {eleve.nom}*.

📋 *Détails de l'abonnement:*
• Élève: {eleve.prenom} {eleve.nom}
• Classe: {eleve.classe.nom if eleve.classe else 'N/A'}
• Périodicité: {abonnement.get_periodicite_display()}
• Montant: *{montant_formate} GNF*
• Date début: {abonnement.date_debut.strftime('%d/%m/%Y')}
• Date expiration: {abonnement.date_expiration.strftime('%d/%m/%Y')}
• Statut: *{abonnement.get_statut_display()}*"""

        if abonnement.zone:
            message += f"""
• Zone: {abonnement.zone}"""
        if abonnement.point_arret:
            message += f"""
• Point d'arrêt: {abonnement.point_arret}"""

        if pdf_url:
            message += f"""

📄 *Télécharger le reçu PDF:*
{pdf_url}"""

        message += """

📞 Pour toute question, contactez-nous."""

        if tel_ecole:
            message += f"""
📱 Tél: {tel_ecole}"""
        if email_ecole:
            message += f"""
📧 Email: {email_ecole}"""

        message += """

Cordialement,
🏫 La Direction"""

        return message
    
    def _generer_message_expiration(self, abonnement, pdf_url=None):
        """Génère le message WhatsApp pour une alerte d'expiration"""
        eleve = abonnement.eleve
        ecole = eleve.classe.ecole if eleve.classe else None
        nom_ecole = ecole.nom if ecole else "École"
        tel_ecole = ecole.tous_telephones if ecole else ""
        email_ecole = ecole.email if ecole else ""
        
        # Formater le montant
        montant_formate = f"{abonnement.montant:,.0f}".replace(",", " ")
        
        # Calculer les jours restants ou de retard
        today = timezone.localdate()
        delta = (abonnement.date_expiration - today).days
        
        if delta < 0:
            etat_expiration = f"⚠️ *EXPIRÉ depuis {abs(delta)} jour(s)*"
            titre = "RAPPEL - Abonnement Bus Expiré"
        elif delta == 0:
            etat_expiration = "⚠️ *EXPIRE AUJOURD'HUI*"
            titre = "URGENT - Abonnement Bus Expire Aujourd'hui"
        else:
            etat_expiration = f"⏳ *Expire dans {delta} jour(s)*"
            titre = "Rappel - Abonnement Bus Proche d'Expiration"
        
        message = f"""🚌 *{nom_ecole} - {titre}*

Bonjour Cher Parent,

Nous vous informons que l'abonnement au bus scolaire de votre enfant *{eleve.prenom} {eleve.nom}* nécessite votre attention.

📋 *Situation de l'abonnement:*
• Élève: {eleve.prenom} {eleve.nom}
• Classe: {eleve.classe.nom if eleve.classe else 'N/A'}
• Date d'expiration: {abonnement.date_expiration.strftime('%d/%m/%Y')}
• {etat_expiration}
• Montant à renouveler: *{montant_formate} GNF*"""

        if abonnement.zone:
            message += f"""
• Zone: {abonnement.zone}"""
        if abonnement.point_arret:
            message += f"""
• Point d'arrêt: {abonnement.point_arret}"""

        if pdf_url:
            message += f"""

📄 *Télécharger le reçu actuel:*
{pdf_url}"""

        message += """

Nous vous prions de bien vouloir procéder au renouvellement dans les meilleurs délais pour assurer la continuité du service de transport.

📞 Pour toute question ou renouvellement, contactez-nous."""

        if tel_ecole:
            message += f"""
📱 Tél: {tel_ecole}"""
        if email_ecole:
            message += f"""
📧 Email: {email_ecole}"""

        message += """

Cordialement,
🏫 La Direction"""

        return message


# Instance globale
whatsapp_bus_sender = WhatsAppBusSender()


@login_required
def apercu_message_whatsapp_abonnement(request):
    """Aperçu du message WhatsApp pour un abonnement bus (confirmation/reçu)"""
    from utilisateurs.utils import user_is_superadmin, filter_by_user_school

    try:
        abo_id = request.GET.get('abo_id')

        if not abo_id:
            return JsonResponse({
                'success': False,
                'error': 'ID abonnement manquant'
            })

        abonnement = get_object_or_404(
            AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole'),
            id=abo_id
        )

        # Sécurité : vérifier l'appartenance à l'école de l'utilisateur
        if not user_is_superadmin(request.user):
            if not filter_by_user_school(
                AbonnementBus.objects.filter(pk=abonnement.pk),
                request.user,
                'eleve__classe__ecole'
            ).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Accès refusé'
                }, status=403)
        eleve = abonnement.eleve
        telephone = whatsapp_bus_sender._get_telephone_parent(eleve)
        
        # Générer l'URL PUBLIQUE du PDF (sans authentification requise - validité 7 jours)
        pdf_url = None
        try:
            from .abonnement_public import generer_url_abonnement_public
            pdf_url = generer_url_abonnement_public(request, abonnement.id)
        except Exception as e:
            logger.warning(f"Impossible de générer l'URL publique du PDF: {e}")
        
        # Générer le message
        message = whatsapp_bus_sender._generer_message_abonnement(abonnement, pdf_url)
        
        # Formater le numéro pour WhatsApp
        whatsapp_number = whatsapp_bus_sender._formater_numero_whatsapp(telephone)
        
        # Générer le lien WhatsApp
        whatsapp_link = None
        if whatsapp_number:
            encoded_message = urllib.parse.quote(message)
            whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+', '')}?text={encoded_message}"
        
        # Formater le montant
        montant_formate = f"{abonnement.montant:,.0f}".replace(",", " ")
        
        return JsonResponse({
            'success': True,
            'message': message,
            'telephone': telephone,
            'whatsapp_number': whatsapp_number,
            'whatsapp_link': whatsapp_link,
            'pdf_url': pdf_url,
            'eleve_nom': f"{eleve.prenom} {eleve.nom}",
            'classe': eleve.classe.nom if eleve.classe else 'N/A',
            'periodicite': abonnement.get_periodicite_display(),
            'montant': montant_formate,
            'date_debut': abonnement.date_debut.strftime('%d/%m/%Y'),
            'date_expiration': abonnement.date_expiration.strftime('%d/%m/%Y'),
            'statut': abonnement.get_statut_display(),
            'zone': abonnement.zone or 'N/A',
            'point_arret': abonnement.point_arret or 'N/A'
        })
        
    except Exception as e:
        logger.error(f"Erreur aperçu message WhatsApp abonnement bus: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors de la génération de l\'aperçu'
        })


@login_required
def apercu_message_whatsapp_expiration(request):
    """Aperçu du message WhatsApp pour une alerte d'expiration"""
    from utilisateurs.utils import user_is_superadmin, filter_by_user_school

    try:
        abo_id = request.GET.get('abo_id')

        if not abo_id:
            return JsonResponse({
                'success': False,
                'error': 'ID abonnement manquant'
            })

        abonnement = get_object_or_404(
            AbonnementBus.objects.select_related('eleve', 'eleve__classe', 'eleve__classe__ecole'),
            id=abo_id
        )

        # Sécurité : vérifier l'appartenance à l'école de l'utilisateur
        if not user_is_superadmin(request.user):
            if not filter_by_user_school(
                AbonnementBus.objects.filter(pk=abonnement.pk),
                request.user,
                'eleve__classe__ecole'
            ).exists():
                return JsonResponse({
                    'success': False,
                    'error': 'Accès refusé'
                }, status=403)
        eleve = abonnement.eleve
        telephone = whatsapp_bus_sender._get_telephone_parent(eleve)
        
        # Générer l'URL PUBLIQUE du PDF (sans authentification requise - validité 7 jours)
        pdf_url = None
        try:
            from .abonnement_public import generer_url_abonnement_public
            pdf_url = generer_url_abonnement_public(request, abonnement.id)
        except Exception as e:
            logger.warning(f"Impossible de générer l'URL publique du PDF: {e}")
        
        # Générer le message d'expiration
        message = whatsapp_bus_sender._generer_message_expiration(abonnement, pdf_url)
        
        # Formater le numéro pour WhatsApp
        whatsapp_number = whatsapp_bus_sender._formater_numero_whatsapp(telephone)
        
        # Générer le lien WhatsApp
        whatsapp_link = None
        if whatsapp_number:
            encoded_message = urllib.parse.quote(message)
            whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+', '')}?text={encoded_message}"
        
        # Formater le montant
        montant_formate = f"{abonnement.montant:,.0f}".replace(",", " ")
        
        # Calculer les jours
        today = timezone.localdate()
        delta = (abonnement.date_expiration - today).days
        if delta < 0:
            jours_info = f"Expiré depuis {abs(delta)} jour(s)"
            statut_expiration = "EXPIRÉ"
        elif delta == 0:
            jours_info = "Expire aujourd'hui"
            statut_expiration = "EXPIRE AUJOURD'HUI"
        else:
            jours_info = f"Expire dans {delta} jour(s)"
            statut_expiration = "PROCHE EXPIRATION"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'telephone': telephone,
            'whatsapp_number': whatsapp_number,
            'whatsapp_link': whatsapp_link,
            'pdf_url': pdf_url,
            'eleve_nom': f"{eleve.prenom} {eleve.nom}",
            'classe': eleve.classe.nom if eleve.classe else 'N/A',
            'periodicite': abonnement.get_periodicite_display(),
            'montant': montant_formate,
            'date_debut': abonnement.date_debut.strftime('%d/%m/%Y'),
            'date_expiration': abonnement.date_expiration.strftime('%d/%m/%Y'),
            'statut': abonnement.get_statut_display(),
            'statut_expiration': statut_expiration,
            'jours_info': jours_info,
            'zone': abonnement.zone or 'N/A',
            'point_arret': abonnement.point_arret or 'N/A'
        })
        
    except Exception as e:
        logger.error(f"Erreur aperçu message WhatsApp expiration bus: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors de la génération de l\'aperçu'
        })
