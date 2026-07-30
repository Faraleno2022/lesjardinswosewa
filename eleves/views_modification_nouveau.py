#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Vue de modification d'élève - Version nouvelle et fonctionnelle
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import logging

from .models import Eleve, HistoriqueEleve
from .forms import EleveForm
from comptes.models import JournalActivite

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET", "POST"])
def modifier_eleve_nouveau(request, eleve_id):
    """
    Vue pour modifier un élève existant - Version nouvelle et fonctionnelle
    """
    try:
        eleve = get_object_or_404(Eleve, id=eleve_id)
        
        if request.method == 'POST':
            return _traiter_modification_post(request, eleve)
        else:
            return _afficher_formulaire_modification(request, eleve)
            
    except Exception as e:
        logger.error(f"Erreur dans modifier_eleve_nouveau: {str(e)}")
        messages.error(request, "Une erreur est survenue lors du chargement du formulaire.")
        return redirect('eleves:liste_eleves')

def _afficher_formulaire_modification(request, eleve):
    """
    Affiche le formulaire de modification pré-rempli
    """
    try:
        # Création du formulaire avec l'instance de l'élève
        form = EleveForm(instance=eleve)
        
        # Contexte pour le template
        context = {
            'form': form,
            'eleve': eleve,
            'page_title': f'Modifier {eleve.prenom} {eleve.nom}',
            'breadcrumb': [
                {'name': 'Accueil', 'url': '/'},
                {'name': 'Élèves', 'url': '/eleves/liste/'},
                {'name': f'{eleve.prenom} {eleve.nom}', 'url': f'/eleves/{eleve.id}/'},
                {'name': 'Modifier', 'url': ''}
            ]
        }
        
        logger.info(f"Affichage du formulaire de modification pour l'élève {eleve.id}")
        return render(request, 'eleves/modifier_eleve_nouveau.html', context)
        
    except Exception as e:
        logger.error(f"Erreur lors de l'affichage du formulaire: {str(e)}")
        messages.error(request, "Erreur lors du chargement du formulaire de modification.")
        return redirect('eleves:detail_eleve', eleve_id=eleve.id)

def _traiter_modification_post(request, eleve):
    """
    Traite la soumission du formulaire de modification
    """
    try:
        with transaction.atomic():
            # Sauvegarde des valeurs originales pour détecter les changements
            valeurs_originales = _sauvegarder_valeurs_originales(eleve)
            
            # Création du formulaire avec les données POST
            form = EleveForm(request.POST, request.FILES, instance=eleve)
            
            if form.is_valid():
                return _sauvegarder_modifications(request, form, eleve, valeurs_originales)
            else:
                return _gerer_erreurs_formulaire(request, form, eleve)
                
    except Exception as e:
        logger.error(f"Erreur lors du traitement POST: {str(e)}")
        messages.error(request, "Une erreur est survenue lors de la sauvegarde.")
        return _afficher_formulaire_modification(request, eleve)

def _sauvegarder_valeurs_originales(eleve):
    """
    Sauvegarde les valeurs originales de l'élève pour détecter les changements
    """
    return {
        'matricule': eleve.matricule,
        'prenom': eleve.prenom,
        'nom': eleve.nom,
        'sexe': eleve.sexe,
        'date_naissance': eleve.date_naissance,
        'lieu_naissance': eleve.lieu_naissance,
        'classe': eleve.classe,
        'date_inscription': eleve.date_inscription,
        'statut': eleve.statut,
        'responsable_principal': eleve.responsable_principal,
        'responsable_secondaire': eleve.responsable_secondaire,
        'photo': eleve.photo.name if eleve.photo else None
    }

def _sauvegarder_modifications(request, form, eleve, valeurs_originales):
    """
    Sauvegarde les modifications et gère l'historique
    """
    try:
        # Sauvegarde de l'élève
        eleve_modifie = form.save()
        
        # Détection des changements
        changements = _detecter_changements(form, valeurs_originales, eleve_modifie)
        
        # Création de l'historique si des changements ont été effectués
        if changements:
            _creer_historique_modification(eleve_modifie, changements, request.user)
            _creer_journal_activite(request, eleve_modifie, changements)
            
            messages.success(
                request, 
                f"Les informations de {eleve_modifie.prenom} {eleve_modifie.nom} ont été mises à jour avec succès. "
                f"({len(changements)} modification{'s' if len(changements) > 1 else ''} effectuée{'s' if len(changements) > 1 else ''})"
            )
        else:
            messages.info(request, "Aucune modification détectée.")
        
        # Redirection selon l'action demandée
        action = request.POST.get('action', 'save')
        if action == 'save_and_list':
            return redirect('eleves:liste_eleves')
        else:
            return redirect('eleves:detail_eleve', eleve_id=eleve_modifie.id)
            
    except Exception as e:
        logger.error(f"Erreur lors de la sauvegarde: {str(e)}")
        messages.error(request, "Erreur lors de la sauvegarde des modifications.")
        raise

def _detecter_changements(form, valeurs_originales, eleve_modifie):
    """
    Détecte les changements effectués sur l'élève
    """
    changements = []
    
    # Mapping des champs avec leurs labels
    champs_labels = {
        'matricule': 'Matricule',
        'prenom': 'Prénom',
        'nom': 'Nom',
        'sexe': 'Sexe',
        'date_naissance': 'Date de naissance',
        'lieu_naissance': 'Lieu de naissance',
        'classe': 'Classe',
        'date_inscription': 'Date d\'inscription',
        'statut': 'Statut',
        'responsable_principal': 'Responsable principal',
        'responsable_secondaire': 'Responsable secondaire',
        'photo': 'Photo'
    }
    
    for champ, label in champs_labels.items():
        valeur_originale = valeurs_originales.get(champ)
        valeur_nouvelle = getattr(eleve_modifie, champ)
        
        # Gestion spéciale pour les champs de relation
        if champ in ['classe', 'responsable_principal', 'responsable_secondaire']:
            valeur_originale_str = str(valeur_originale) if valeur_originale else 'Aucun(e)'
            valeur_nouvelle_str = str(valeur_nouvelle) if valeur_nouvelle else 'Aucun(e)'
        # Gestion spéciale pour la photo
        elif champ == 'photo':
            valeur_originale_str = 'Oui' if valeur_originale else 'Non'
            valeur_nouvelle_str = 'Oui' if (valeur_nouvelle and valeur_nouvelle.name) else 'Non'
        # Gestion normale pour les autres champs
        else:
            valeur_originale_str = str(valeur_originale) if valeur_originale is not None else ''
            valeur_nouvelle_str = str(valeur_nouvelle) if valeur_nouvelle is not None else ''
        
        if valeur_originale_str != valeur_nouvelle_str:
            changements.append({
                'champ': champ,
                'label': label,
                'ancien': valeur_originale_str,
                'nouveau': valeur_nouvelle_str
            })
    
    return changements

def _creer_historique_modification(eleve, changements, utilisateur):
    """
    Crée une entrée dans l'historique des modifications
    """
    try:
        description_changements = []
        for changement in changements:
            description_changements.append(
                f"{changement['label']}: {changement['ancien']} → {changement['nouveau']}"
            )
        
        HistoriqueEleve.objects.create(
            eleve=eleve,
            action='MODIFICATION',
            description=f"Modification: {', '.join(description_changements)}",
            utilisateur=utilisateur
        )
        
        logger.info(f"Historique créé pour l'élève {eleve.id} par {utilisateur.username}")
        
    except Exception as e:
        logger.error(f"Erreur lors de la création de l'historique: {str(e)}")

def _creer_journal_activite(request, eleve, changements):
    """
    Crée une entrée dans le journal d'activité
    """
    try:
        description_changements = [f"{c['label']}: {c['ancien']} → {c['nouveau']}" for c in changements]
        
        JournalActivite.objects.create(
            user=request.user,
            action='MODIFICATION',
            type_objet='ELEVE',
            objet_id=eleve.id,
            description=f"Modification de l'élève {eleve.prenom} {eleve.nom}: {', '.join(description_changements)}",
            adresse_ip=request.META.get('REMOTE_ADDR', ''),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        logger.info(f"Journal d'activité créé pour la modification de l'élève {eleve.id}")
        
    except Exception as e:
        logger.error(f"Erreur lors de la création du journal d'activité: {str(e)}")

def _gerer_erreurs_formulaire(request, form, eleve):
    """
    Gère les erreurs de validation du formulaire
    """
    try:
        # Compter les erreurs
        nb_erreurs = sum(len(errors) for errors in form.errors.values())
        
        messages.error(
            request, 
            f"Le formulaire contient {nb_erreurs} erreur{'s' if nb_erreurs > 1 else ''}. "
            "Veuillez corriger les champs indiqués en rouge."
        )
        
        # Log des erreurs pour le débogage
        for champ, erreurs in form.errors.items():
            logger.warning(f"Erreur formulaire - {champ}: {erreurs}")
        
        # Réaffichage du formulaire avec les erreurs
        context = {
            'form': form,
            'eleve': eleve,
            'page_title': f'Modifier {eleve.prenom} {eleve.nom}',
            'form_errors': True
        }
        
        return render(request, 'eleves/modifier_eleve_nouveau.html', context)
        
    except Exception as e:
        logger.error(f"Erreur lors de la gestion des erreurs de formulaire: {str(e)}")
        messages.error(request, "Une erreur est survenue lors de la validation du formulaire.")
        return redirect('eleves:detail_eleve', eleve_id=eleve.id)

@login_required
def ajax_valider_champ(request):
    """
    Validation AJAX d'un champ spécifique (optionnel)
    """
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            champ = request.POST.get('champ')
            valeur = request.POST.get('valeur')
            eleve_id = request.POST.get('eleve_id')
            
            if not all([champ, eleve_id]):
                return JsonResponse({'valid': False, 'message': 'Paramètres manquants'})
            
            eleve = get_object_or_404(Eleve, id=eleve_id)
            
            # Création d'un formulaire temporaire pour validation
            data = {champ: valeur}
            form = EleveForm(data=data, instance=eleve)
            
            if champ in form.errors:
                return JsonResponse({
                    'valid': False, 
                    'message': form.errors[champ][0]
                })
            else:
                return JsonResponse({'valid': True})
                
        except Exception as e:
            logger.error(f"Erreur validation AJAX: {str(e)}")
            return JsonResponse({'valid': False, 'message': 'Erreur de validation'})
    
    return JsonResponse({'valid': False, 'message': 'Requête invalide'})
