from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
import uuid
import json
import logging

from .models import Matiere, DocumentCours, ConversationChat, MessageChat, RecherchePopulaire
from .search_engine import (
    rechercher_dans_documents,
    generer_reponse,
    enregistrer_recherche,
    obtenir_suggestions_populaires
)
from .document_processor import traiter_document_upload, valider_fichier

logger = logging.getLogger(__name__)


def _get_user_ecole(request):
    """Retourne l'école de l'utilisateur connecté, ou None"""
    if request.user.is_authenticated:
        try:
            from utilisateurs.utils import user_school
            return user_school(request.user)
        except Exception:
            pass
    return None


def _filter_documents_by_school(qs, ecole):
    """Filtre les documents par école via uploaded_by__profil__ecole"""
    if ecole:
        return qs.filter(uploaded_by__profil__ecole=ecole)
    return qs


def get_or_create_session_id(request):
    """Obtient ou crée un ID de session pour les utilisateurs non connectés"""
    session_id = request.session.get('chatbot_session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        request.session['chatbot_session_id'] = session_id
    return session_id


@login_required
def chatbot_home(request):
    """Page d'accueil du chatbot éducatif"""
    ecole = _get_user_ecole(request)

    matieres = Matiere.objects.filter(actif=True).annotate(
        nb_documents=Count('documents', filter=Q(documents__actif=True))
    )

    # Statistiques — filtrées par école
    docs_qs = DocumentCours.objects.filter(actif=True)
    docs_qs = _filter_documents_by_school(docs_qs, ecole)

    stats = {
        'total_documents': docs_qs.count(),
        'total_matieres': matieres.count(),
        'documents_recents': docs_qs.order_by('-date_upload')[:5]
    }

    # Suggestions populaires
    suggestions = obtenir_suggestions_populaires(limite=6)

    context = {
        'matieres': matieres,
        'stats': stats,
        'suggestions': suggestions,
        'page_title': 'Chatbot Révision',
    }
    return render(request, 'chatbot/home.html', context)


@login_required
def chat_interface(request, matiere_id=None):
    """Interface de chat pour une matière spécifique ou générale"""
    ecole = _get_user_ecole(request)
    matieres = Matiere.objects.filter(actif=True)
    matiere_selectionnee = None

    if matiere_id:
        matiere_selectionnee = get_object_or_404(Matiere, id=matiere_id, actif=True)

    # Récupérer ou créer une conversation
    conversation, created = ConversationChat.objects.get_or_create(
        utilisateur=request.user,
        matiere=matiere_selectionnee,
        active=True,
        defaults={'date_debut': timezone.now()}
    )

    # Récupérer les messages de la conversation
    messages_chat = conversation.messages.all().order_by('date_envoi')

    # Documents disponibles pour cette matière — filtrés par école
    documents = DocumentCours.objects.filter(actif=True)
    documents = _filter_documents_by_school(documents, ecole)
    if matiere_selectionnee:
        documents = documents.filter(matiere=matiere_selectionnee)

    context = {
        'matieres': matieres,
        'matiere_selectionnee': matiere_selectionnee,
        'conversation': conversation,
        'messages_chat': messages_chat,
        'documents_count': documents.count(),
        'niveaux': DocumentCours.NIVEAU_CHOICES,
        'page_title': f'Chat - {matiere_selectionnee.nom}' if matiere_selectionnee else 'Chat Révision',
    }
    return render(request, 'chatbot/chat.html', context)


@login_required
@require_http_methods(["POST"])
def envoyer_message(request):
    """API pour envoyer un message et recevoir une réponse"""
    try:
        data = json.loads(request.body)
        question = data.get('message', '').strip()
        matiere_id = data.get('matiere_id')
        conversation_id = data.get('conversation_id')
        niveau = data.get('niveau')

        if not question:
            return JsonResponse({'error': 'Message vide'}, status=400)

        # Limiter la longueur de la question
        if len(question) > 2000:
            return JsonResponse({'error': 'Message trop long (max 2000 caractères)'}, status=400)

        # Récupérer ou créer la conversation
        conversation = None
        if conversation_id:
            try:
                # Sécurité : vérifier que la conversation appartient à l'utilisateur
                conversation = ConversationChat.objects.get(
                    id=conversation_id,
                    utilisateur=request.user
                )
            except ConversationChat.DoesNotExist:
                conversation = None

        if not conversation:
            conversation = ConversationChat.objects.create(
                utilisateur=request.user,
                matiere_id=matiere_id
            )

        # Sauvegarder le message de l'utilisateur
        message_user = MessageChat.objects.create(
            conversation=conversation,
            type_message='USER',
            contenu=question
        )

        # Rechercher dans les documents
        resultats = rechercher_dans_documents(
            question=question,
            matiere_id=matiere_id,
            niveau=niveau
        )

        # Générer la réponse
        reponse_data = generer_reponse(question, resultats)

        # Sauvegarder la réponse du bot
        message_bot = MessageChat.objects.create(
            conversation=conversation,
            type_message='BOT',
            contenu=reponse_data['reponse']
        )

        # Ajouter les documents référencés
        for doc in reponse_data['documents']:
            message_bot.documents_references.add(doc)
            doc.nombre_consultations += 1
            doc.save(update_fields=['nombre_consultations'])

        # Enregistrer la recherche pour les statistiques
        enregistrer_recherche(question, matiere_id)

        # Mettre à jour la date d'activité de la conversation
        conversation.date_derniere_activite = timezone.now()
        conversation.save(update_fields=['date_derniere_activite'])

        return JsonResponse({
            'success': True,
            'reponse': reponse_data['reponse'],
            'confiance': reponse_data['confiance'],
            'documents': [
                {
                    'id': doc.id,
                    'titre': doc.titre,
                    'matiere': doc.matiere.nom,
                    'niveau': doc.get_niveau_display()
                }
                for doc in reponse_data['documents']
            ],
            'suggestions': reponse_data['suggestions'],
            'conversation_id': conversation.id,
            'message_id': message_bot.id
        })

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Format JSON invalide'}, status=400)
    except Exception as e:
        logger.error(f"Erreur envoyer_message chatbot: {e}", exc_info=True)
        return JsonResponse({'error': 'Une erreur est survenue. Veuillez réessayer.'}, status=500)


@login_required
def liste_documents(request):
    """Liste tous les documents disponibles"""
    ecole = _get_user_ecole(request)
    matieres = Matiere.objects.filter(actif=True)
    matiere_id = request.GET.get('matiere')
    niveau = request.GET.get('niveau')
    recherche = request.GET.get('q', '').strip()

    documents = DocumentCours.objects.filter(actif=True).select_related('matiere', 'uploaded_by')
    # Sécurité : filtrer par école
    documents = _filter_documents_by_school(documents, ecole)

    if matiere_id:
        documents = documents.filter(matiere_id=matiere_id)
    
    if niveau:
        documents = documents.filter(niveau=niveau)
    
    if recherche:
        documents = documents.filter(
            Q(titre__icontains=recherche) |
            Q(description__icontains=recherche)
        )
    
    # Pagination
    paginator = Paginator(documents, 12)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'documents': documents_page,
        'matieres': matieres,
        'matiere_selectionnee': matiere_id,
        'niveau_selectionne': niveau,
        'recherche': recherche,
        'niveaux': DocumentCours.NIVEAU_CHOICES,
        'page_title': 'Documents de cours',
    }
    return render(request, 'chatbot/documents.html', context)


@login_required
def detail_document(request, document_id):
    """Affiche les détails d'un document"""
    document = get_object_or_404(
        DocumentCours.objects.select_related('matiere', 'uploaded_by'),
        id=document_id, actif=True
    )

    # Sécurité : vérifier l'appartenance à l'école
    ecole = _get_user_ecole(request)
    if ecole and document.uploaded_by:
        profil = getattr(document.uploaded_by, 'profil', None)
        if profil and profil.ecole != ecole:
            from django.http import Http404
            raise Http404("Document non trouvé")
    
    # Incrémenter le compteur de consultations
    document.nombre_consultations += 1
    document.save(update_fields=['nombre_consultations'])
    
    # Documents similaires (même matière)
    documents_similaires = DocumentCours.objects.filter(
        matiere=document.matiere,
        actif=True
    ).exclude(id=document.id)[:4]
    
    context = {
        'document': document,
        'documents_similaires': documents_similaires,
        'page_title': document.titre,
    }
    return render(request, 'chatbot/detail_document.html', context)


@staff_member_required
def gestion_documents(request):
    """Interface d'administration des documents (staff uniquement)"""
    ecole = _get_user_ecole(request)
    matieres = Matiere.objects.annotate(nb_documents=Count('documents'))
    documents = DocumentCours.objects.all().select_related('matiere', 'uploaded_by').order_by('-date_upload')
    # Sécurité : filtrer par école
    documents = _filter_documents_by_school(documents, ecole)
    
    # Pagination
    paginator = Paginator(documents, 20)
    page = request.GET.get('page', 1)
    documents_page = paginator.get_page(page)
    
    context = {
        'matieres': matieres,
        'documents': documents_page,
        'niveaux': DocumentCours.NIVEAU_CHOICES,
        'page_title': 'Gestion des documents',
    }
    return render(request, 'chatbot/gestion_documents.html', context)


@staff_member_required
@require_http_methods(["GET", "POST"])
def ajouter_document(request):
    """Ajouter un nouveau document"""
    if request.method == 'POST':
        titre = request.POST.get('titre', '').strip()
        description = request.POST.get('description', '').strip()
        matiere_id = request.POST.get('matiere')
        niveau = request.POST.get('niveau', 'TOUS')
        fichier = request.FILES.get('fichier')
        
        # Validation
        erreurs = []
        if not titre:
            erreurs.append("Le titre est obligatoire")
        if not matiere_id:
            erreurs.append("La matière est obligatoire")
        if not fichier:
            erreurs.append("Le fichier est obligatoire")
        else:
            valide, msg = valider_fichier(fichier)
            if not valide:
                erreurs.append(msg)
        
        if erreurs:
            for erreur in erreurs:
                messages.error(request, erreur)
        else:
            try:
                matiere = Matiere.objects.get(id=matiere_id)
                document = DocumentCours.objects.create(
                    titre=titre,
                    description=description,
                    matiere=matiere,
                    niveau=niveau,
                    fichier=fichier,
                    uploaded_by=request.user
                )
                
                # Extraire le contenu du document
                succes = traiter_document_upload(document)
                
                if succes:
                    messages.success(request, f"Document '{titre}' ajouté avec succès!")
                else:
                    messages.warning(request, f"Document ajouté mais l'extraction du contenu a échoué. Vérifiez le format du fichier.")

                # Redirection sécurisée : valider que next_url est interne
                next_url = request.POST.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    return redirect(next_url)
                return redirect('chatbot:gestion_documents')

            except Matiere.DoesNotExist:
                messages.error(request, "Matière invalide")
            except Exception as e:
                logger.error(f"Erreur ajout document chatbot: {e}", exc_info=True)
                messages.error(request, "Erreur lors de l'ajout du document. Veuillez réessayer.")
    
    matieres = Matiere.objects.filter(actif=True)
    context = {
        'matieres': matieres,
        'niveaux': DocumentCours.NIVEAU_CHOICES,
        'page_title': 'Ajouter un document',
    }
    return render(request, 'chatbot/ajouter_document.html', context)


@staff_member_required
@require_http_methods(["POST"])
def supprimer_document(request, document_id):
    """Supprimer un document"""
    document = get_object_or_404(DocumentCours.objects.select_related('uploaded_by'), id=document_id)

    # Sécurité : vérifier l'appartenance à l'école
    ecole = _get_user_ecole(request)
    if ecole and document.uploaded_by:
        profil = getattr(document.uploaded_by, 'profil', None)
        if profil and profil.ecole != ecole:
            messages.error(request, "Accès refusé.")
            return redirect('chatbot:gestion_documents')

    titre = document.titre

    # Soft delete
    document.actif = False
    document.save(update_fields=['actif'])

    messages.success(request, f"Document '{titre}' supprimé")
    return redirect('chatbot:gestion_documents')


@staff_member_required
@require_http_methods(["GET", "POST"])
def gestion_matieres(request):
    """Gestion des matières"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'ajouter':
            nom = request.POST.get('nom', '').strip()
            description = request.POST.get('description', '').strip()
            icone = request.POST.get('icone', '📚').strip()
            
            if nom:
                Matiere.objects.create(
                    nom=nom,
                    description=description,
                    icone=icone
                )
                messages.success(request, f"Matière '{nom}' ajoutée")
            else:
                messages.error(request, "Le nom est obligatoire")
        
        elif action == 'supprimer':
            matiere_id = request.POST.get('matiere_id')
            try:
                matiere = Matiere.objects.get(id=matiere_id)
                matiere.actif = False
                matiere.save(update_fields=['actif'])
                messages.success(request, f"Matière '{matiere.nom}' désactivée")
            except Matiere.DoesNotExist:
                messages.error(request, "Matière non trouvée")
        
        return redirect('chatbot:gestion_matieres')
    
    matieres = Matiere.objects.annotate(nb_documents=Count('documents'))
    
    context = {
        'matieres': matieres,
        'page_title': 'Gestion des matières',
    }
    return render(request, 'chatbot/gestion_matieres.html', context)


@login_required
def nouvelle_conversation(request):
    """Démarre une nouvelle conversation"""
    matiere_id = request.GET.get('matiere')

    # Désactiver les anciennes conversations de l'utilisateur
    ConversationChat.objects.filter(
        utilisateur=request.user,
        active=True
    ).update(active=False)

    if matiere_id:
        return redirect('chatbot:chat_matiere', matiere_id=matiere_id)
    return redirect('chatbot:chat')


@login_required
def api_matieres(request):
    """API pour récupérer la liste des matières"""
    matieres = Matiere.objects.filter(actif=True).values('id', 'nom', 'icone', 'description')
    return JsonResponse({'matieres': list(matieres)})


@login_required
def api_suggestions(request):
    """API pour récupérer des suggestions de questions"""
    matiere_id = request.GET.get('matiere')
    suggestions = obtenir_suggestions_populaires(matiere_id=matiere_id, limite=5)
    return JsonResponse({'suggestions': suggestions})
