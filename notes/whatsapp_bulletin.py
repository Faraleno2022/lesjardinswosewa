"""
Module pour l'envoi de bulletins PDF par WhatsApp aux parents
"""

import os
import tempfile
import logging
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.template.loader import render_to_string
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from decimal import Decimal

from eleves.models import Eleve, Classe as ClasseEleve
from .models import MatiereNote, NoteEleve, Evaluation, ClasseNote
from .calculs_moyennes import (
    calculer_moyenne_generale_eleve, 
    calculer_classement_classe,
    calculer_moyenne_annuelle_matiere,
    detecter_niveau_scolaire,
    calculer_bulletin_intelligent
)
from paiements.models import Relance

logger = logging.getLogger(__name__)

class WhatsAppBulletinSender:
    """Gestionnaire pour l'envoi de bulletins par WhatsApp"""
    
    def __init__(self):
        self.temp_files = []  # Pour nettoyer les fichiers temporaires
    
    def generer_bulletin_pdf(self, eleve_id, classe_id, periode, system_type='trimestre'):
        """
        Génère le bulletin HTML pour un élève (alternative au PDF)
        Supporte les bulletins mensuels, trimestriels, semestriels et annuels.
        
        Returns:
            tuple: (file_path, filename) ou (None, None) si erreur
        """
        try:
            # Récupérer l'élève et la classe
            eleve = get_object_or_404(Eleve, id=eleve_id)
            classe_eleve = get_object_or_404(ClasseEleve, id=classe_id)
            
            # Essayer de récupérer la ClasseNote correspondante
            classe_note = None
            try:
                classe_note = ClasseNote.objects.filter(nom=classe_eleve.nom).first()
            except:
                pass
            
            # Récupérer les matières
            try:
                if classe_note:
                    matieres = MatiereNote.objects.filter(classe=classe_note, actif=True).order_by('nom')
                else:
                    matieres = MatiereNote.objects.filter(classe__nom=classe_eleve.nom, actif=True).order_by('nom')
            except:
                matieres = MatiereNote.objects.filter(actif=True)[:10]
            
            if not matieres.exists():
                logger.error(f"Aucune matière trouvée pour la classe {classe_eleve.nom}")
                return None, None
            
            # Détecter le niveau scolaire
            niveau_detecte = detecter_niveau_scolaire(classe_eleve.nom)
            est_primaire = (niveau_detecte == 'PRIMAIRE')
            est_maternelle = (niveau_detecte == 'MATERNELLE')
            
            # Calculer les données du bulletin avec la fonction centralisée
            matieres_notes = []
            total_points = Decimal('0')
            total_coefficients = Decimal('0')
            
            for matiere in matieres:
                # Utiliser la fonction centralisée intelligente
                result = calculer_bulletin_intelligent(eleve, matiere, periode, system_type)
                
                coefficient_effectif = Decimal(str(result['coefficient']))
                
                # Accumuler les totaux
                if result['moyenne'] is not None:
                    total_points += Decimal(str(result['moyenne'])) * coefficient_effectif
                    total_coefficients += coefficient_effectif
                
                matieres_notes.append({
                    'matiere': matiere,
                    'moyenne': result['moyenne'],
                    'moyenne_continue': result['moyenne_continue'],
                    'note_composition': result['note_composition'],
                    'moyennes_mensuelles': result['moyennes_mensuelles'],
                    'coefficient': result['coefficient'],
                    'points': result['points'],
                })
            
            # Calculer la moyenne générale (pour bulletins non-annuels)
            moyenne_generale = None
            if total_coefficients > 0:
                moyenne_generale = round(float(total_points / total_coefficients), 2)
            
            # CALCUL UNIQUE: Utiliser UNE SEULE SOURCE pour garantir la cohérence moyenne/rang
            from notes.calculs_moyennes import calculer_classement_classe, obtenir_mention_intelligente
            from notes.bulletin_intelligent import formater_rang_intelligent
            
            eleves_classe = list(Eleve.objects.filter(classe=classe_eleve, statut='ACTIF'))
            total_eleves = len(eleves_classe)
            
            # Le classement calcule les moyennes ET les rangs avec la même source
            classement_result = calculer_classement_classe(eleves_classe, matieres, periode, system_type)
            rang_map = classement_result.get('rang_map', {})
            details_map = classement_result.get('details_par_eleve', {})
            
            # Récupérer les données de l'élève depuis le classement (MÊME SOURCE)
            if eleve.id in details_map:
                details_eleve = details_map[eleve.id]
                moyenne_generale = details_eleve.get('moyenne_generale')
                total_points = Decimal(str(details_eleve.get('total_points', 0)))
                total_coefficients = Decimal(str(details_eleve.get('total_coefficients', 0)))
            
            # Récupérer le rang de l'élève (MÊME SOURCE que la moyenne)
            rang_brut = rang_map.get(eleve.id, '-')
            if rang_brut and rang_brut != '-':
                sexe = getattr(eleve, 'sexe', 'M')
                rang_eleve = formater_rang_intelligent(rang_brut, sexe, total_eleves)
            else:
                rang_eleve = "-"
            
            # Calculer la mention basée sur la moyenne (cohérente)
            mention = obtenir_mention_intelligente(moyenne_generale, niveau_detecte) if moyenne_generale else 'N/A'
            
            # Préparer les données pour le template
            bulletin_data = {
                'eleve': eleve,
                'moyenne_generale': moyenne_generale,
                'matieres_notes': matieres_notes,
                'total_points': float(total_points),
                'total_coefficients': float(total_coefficients),
                'rang': rang_eleve,
                'mention': mention,
                'appreciation': 'Bon travail. Continuez vos efforts.',
                'effectif': total_eleves,
                'titre_periode': self._get_titre_periode(periode, system_type)
            }
            
            # Récupérer l'école
            ecole = eleve.classe.ecole if eleve.classe else None
            
            # Déterminer niveau_enseignement
            niveau_enseignement = 'SECONDAIRE'
            if est_maternelle:
                niveau_enseignement = 'MATERNELLE'
            elif est_primaire:
                niveau_enseignement = 'PRIMAIRE'
            
            # Préparer le contexte pour le template
            context = {
                'bulletin_data': bulletin_data,
                'classe_selectionnee': classe_note or classe_eleve,
                'periode_selectionnee': periode,
                'periode': periode,
                'system_type': system_type,
                'niveau_enseignement': niveau_enseignement,
                'est_primaire': est_primaire,
                'est_maternelle': est_maternelle,
                'ecole': ecole,
                'annee_scolaire': classe_eleve.annee_scolaire if hasattr(classe_eleve, 'annee_scolaire') else timezone.now().year,
            }
            
            # Générer le HTML
            html_string = render_to_string('notes/bulletin_dynamique.html', context)
            
            # Créer un fichier temporaire HTML
            with tempfile.NamedTemporaryFile(delete=False, suffix='.html', prefix='bulletin_') as temp_file:
                temp_path = temp_file.name
                temp_file.write(html_string.encode('utf-8'))
                temp_file.flush()
                self.temp_files.append(temp_path)
                
                filename = f"bulletin_{eleve.prenom}_{eleve.nom}_{periode}.html"
                filename = filename.replace(' ', '_').replace('/', '_')
                
                return temp_path, filename
                
        except Exception as e:
            logger.error(f"Erreur lors de la génération du bulletin HTML: {e}")
            return None, None
    
    def _get_titre_periode(self, periode, system_type):
        """Retourne le titre formaté de la période"""
        periodes_map = {
            'mensuel': {
                'OCTOBRE': 'Octobre', 'NOVEMBRE': 'Novembre', 'DECEMBRE': 'Décembre',
                'JANVIER': 'Janvier', 'FEVRIER': 'Février', 'MARS': 'Mars',
                'AVRIL': 'Avril', 'MAI': 'Mai'
            },
            'trimestre': {
                'TRIMESTRE_1': '1er Trimestre', 'TRIMESTRE_2': '2ème Trimestre', 'TRIMESTRE_3': '3ème Trimestre'
            },
            'semestre': {
                'SEMESTRE_1': '1er Semestre', 'SEMESTRE_2': '2ème Semestre'
            },
            'annuel': {
                'ANNUEL': 'Année Complète'
            }
        }
        
        return periodes_map.get(system_type, {}).get(periode, periode)
    
    def envoyer_whatsapp_bulletin(self, eleve_id, classe_id, periode, system_type, utilisateur=None):
        """
        Envoie le bulletin par WhatsApp au parent
        
        Returns:
            dict: Résultat de l'envoi avec succès/erreur
        """
        try:
            # Récupérer l'élève
            eleve = get_object_or_404(Eleve, id=eleve_id)
            
            # Vérifier si l'élève a un numéro WhatsApp
            telephone_parent = self._get_telephone_parent(eleve)
            if not telephone_parent:
                return {
                    'success': False,
                    'error': 'Aucun numéro de téléphone trouvé pour les parents'
                }
            
            # Générer le PDF du bulletin
            pdf_path, filename = self.generer_bulletin_pdf(eleve_id, classe_id, periode, system_type)
            
            if not pdf_path:
                return {
                    'success': False,
                    'error': 'Impossible de générer le bulletin PDF'
                }
            
            # Préparer le message WhatsApp
            message = self._generer_message_whatsapp(eleve, periode, system_type)
            
            # Simuler l'envoi WhatsApp (à remplacer par l'API réelle)
            envoi_reussi = self._simuler_envoi_whatsapp(telephone_parent, message, pdf_path)
            
            if envoi_reussi:
                # Enregistrer dans l'historique des relances
                self._enregistrer_relance(eleve, message, utilisateur)
                
                return {
                    'success': True,
                    'message': f'Bulletin envoyé avec succès au {telephone_parent}',
                    'telephone': telephone_parent
                }
            else:
                return {
                    'success': False,
                    'error': 'Échec de l\'envoi WhatsApp'
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi WhatsApp: {e}")
            return {
                'success': False,
                'error': f'Erreur technique: {str(e)}'
            }
        finally:
            # Nettoyer les fichiers temporaires
            self._cleanup_temp_files()
    
    def _get_telephone_parent(self, eleve):
        """Récupère le numéro de téléphone du parent"""
        # Priorité : Responsable principal > Responsable secondaire
        if eleve.responsable_principal and eleve.responsable_principal.telephone:
            return eleve.responsable_principal.telephone
        elif hasattr(eleve, 'responsable_secondaire') and eleve.responsable_secondaire and eleve.responsable_secondaire.telephone:
            return eleve.responsable_secondaire.telephone
        else:
            return None
    
    def _generer_message_whatsapp(self, eleve, periode, system_type, moyenne=None, rang=None, mention=None, pdf_url=None):
        """Génère le message WhatsApp personnalisé avec les infos de l'école et le lien PDF"""
        titre_periode = self._get_titre_periode(periode, system_type)
        
        # Récupérer les infos de l'école
        ecole = eleve.classe.ecole if eleve.classe else None
        nom_ecole = ecole.nom if ecole else "École"
        tel_ecole = ecole.tous_telephones if ecole else ""
        email_ecole = ecole.email if ecole else ""
        
        # Construire le message
        message = f"""🏫 *{nom_ecole} - Bulletin de Notes*

Bonjour Cher Parent,

Nous avons le plaisir de vous transmettre les résultats de votre enfant *{eleve.prenom} {eleve.nom}* pour la période *{titre_periode}*."""

        # Ajouter les résultats si disponibles
        if moyenne is not None:
            message += f"""

📊 *Résultats:*
• Moyenne Générale: *{moyenne}/20*"""
            if rang:
                message += f"""
• Rang: *{rang}*"""
            if mention:
                message += f"""
• Mention: *{mention}*"""

        # Ajouter le lien vers le PDF
        if pdf_url:
            message += f"""

📄 *Télécharger le bulletin PDF:*
{pdf_url}"""

        message += f"""

📞 Pour toute question, n'hésitez pas à nous contacter."""

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
    
    def _simuler_envoi_whatsapp(self, telephone, message, file_path):
        """
        Simule l'envoi WhatsApp (à remplacer par l'API réelle)
        
        Pour l'implémentation réelle, utiliser:
        - WhatsApp Business API
        - Twilio WhatsApp API
        - Ou autre service
        """
        try:
            # Simulation : toujours réussi pour les tests
            logger.info(f"Simulation envoi WhatsApp vers {telephone}")
            logger.info(f"Message: {message[:100]}...")
            logger.info(f"Fichier bulletin: {file_path}")
            
            # TODO: Remplacer par l'API réelle
            # Exemple avec Twilio:
            # from twilio.rest import Client
            # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            # 
            # # Uploader le fichier
            # with open(file_path, 'rb') as f:
            #     media = client.media.create(content_type='text/html', body=f.read())
            # 
            # # Envoyer le message avec le fichier
            # message = client.messages.create(
            #     body=message,
            #     from_='whatsapp:+14155238886',  # Numéro Twilio WhatsApp
            #     to=f'whatsapp:{telephone}',
            #     media_url=[media.uri]
            # )
            
            return True  # Simulation réussie
            
        except Exception as e:
            logger.error(f"Erreur simulation WhatsApp: {e}")
            return False
    
    def _enregistrer_relance(self, eleve, message, utilisateur):
        """Enregistre l'envoi dans l'historique des relances"""
        try:
            Relance.objects.create(
                eleve=eleve,
                canal='WHATSAPP',
                message=message,
                statut='ENVOYEE',
                solde_estime=Decimal('0'),  # Bulletin, pas de paiement
                cree_par=utilisateur,
                date_envoi=timezone.now()
            )
        except Exception as e:
            logger.error(f"Erreur enregistrement relance: {e}")
    
    def _cleanup_temp_files(self):
        """Nettoie les fichiers temporaires"""
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.error(f"Erreur suppression fichier temporaire {temp_file}: {e}")
        self.temp_files.clear()

# Instance globale
whatsapp_sender = WhatsAppBulletinSender()

@login_required
@require_POST
def envoyer_bulletin_whatsapp(request):
    """Vue pour envoyer le bulletin par WhatsApp"""
    try:
        eleve_id = request.POST.get('eleve_id')
        classe_id = request.POST.get('classe_id')
        periode = request.POST.get('periode')
        system_type = request.POST.get('system_type', 'trimestre')
        
        if not all([eleve_id, classe_id, periode]):
            return JsonResponse({
                'success': False,
                'error': 'Paramètres manquants'
            })
        
        # Envoyer le bulletin
        result = whatsapp_sender.envoyer_whatsapp_bulletin(
            eleve_id, classe_id, periode, system_type, request.user
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Erreur vue envoyer_bulletin_whatsapp: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur technique lors de l\'envoi'
        })

@login_required
def apercu_message_whatsapp(request):
    """Aperçu du message WhatsApp avant envoi avec lien PDF"""
    try:
        eleve_id = request.GET.get('eleve_id')
        classe_id = request.GET.get('classe_id')
        periode = request.GET.get('periode')
        system_type = request.GET.get('system_type', 'trimestre')
        
        if not eleve_id:
            return JsonResponse({
                'success': False,
                'error': 'ID élève manquant'
            })
        
        eleve = get_object_or_404(Eleve, id=eleve_id)
        telephone = whatsapp_sender._get_telephone_parent(eleve)
        
        # Récupérer les résultats de l'élève depuis utils_rangs
        moyenne = None
        rang = None
        mention = None
        classe_note = None
        
        try:
            from .models import ClasseNote
            from .utils_rangs import calculer_rangs_classe_periode
            
            # Trouver la ClasseNote correspondante
            if classe_id:
                classe_note = ClasseNote.objects.filter(id=classe_id).first()
            
            if not classe_note and eleve.classe:
                classe_note = ClasseNote.objects.filter(
                    nom=eleve.classe.nom,
                    annee_scolaire=eleve.classe.annee_scolaire,
                    ecole=eleve.classe.ecole
                ).first()
            
            if classe_note and periode:
                rangs_dict = calculer_rangs_classe_periode(classe_note, periode, use_cache=True)
                rang_info = rangs_dict.get(eleve.id)
                
                if rang_info:
                    moyenne = float(rang_info['moyenne'])
                    rang = f"{rang_info['rang']}/{rang_info['total_eleves']}"
                    
                    # Calculer la mention
                    if moyenne >= 18:
                        mention = "Excellent"
                    elif moyenne >= 16:
                        mention = "Très Bien"
                    elif moyenne >= 14:
                        mention = "Bien"
                    elif moyenne >= 12:
                        mention = "Assez Bien"
                    elif moyenne >= 10:
                        mention = "Passable"
                    elif moyenne >= 8:
                        mention = "Insuffisant"
                    elif moyenne >= 6:
                        mention = "Faible"
                    else:
                        mention = "Très faible"
        except Exception as e:
            logger.warning(f"Impossible de récupérer les résultats: {e}")
        
        # Générer l'URL PUBLIQUE du PDF du bulletin (sans authentification requise)
        pdf_url = None
        try:
            from .bulletin_public import generer_url_bulletin_public
            if classe_note:
                # Utiliser l'URL publique avec token sécurisé
                pdf_url = generer_url_bulletin_public(request, eleve.id, classe_note.id, periode)
        except Exception as e:
            logger.warning(f"Impossible de générer l'URL publique du PDF: {e}")
        
        # Générer le message avec les résultats et le lien PDF
        message = whatsapp_sender._generer_message_whatsapp(eleve, periode, system_type, moyenne, rang, mention, pdf_url)
        
        # Formater le numéro pour WhatsApp (enlever les espaces, ajouter +224 si nécessaire)
        whatsapp_number = None
        if telephone:
            # Nettoyer le numéro
            clean_number = telephone.replace(' ', '').replace('-', '').replace('.', '')
            # Ajouter le code pays si nécessaire
            if not clean_number.startswith('+'):
                if clean_number.startswith('00'):
                    clean_number = '+' + clean_number[2:]
                elif clean_number.startswith('224'):
                    clean_number = '+' + clean_number
                else:
                    clean_number = '+224' + clean_number
            whatsapp_number = clean_number
        
        # Générer le lien WhatsApp
        import urllib.parse
        whatsapp_link = None
        if whatsapp_number:
            encoded_message = urllib.parse.quote(message)
            whatsapp_link = f"https://wa.me/{whatsapp_number.replace('+', '')}?text={encoded_message}"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'telephone': telephone,
            'whatsapp_number': whatsapp_number,
            'whatsapp_link': whatsapp_link,
            'pdf_url': pdf_url,
            'eleve_nom': f"{eleve.prenom} {eleve.nom}",
            'moyenne': moyenne,
            'rang': rang,
            'mention': mention
        })
        
    except Exception as e:
        logger.error(f"Erreur aperçu message WhatsApp: {e}")
        return JsonResponse({
            'success': False,
            'error': 'Erreur lors de la génération de l\'aperçu'
        })
