"""
Vues pour la gestion des permissions granulaires des comptables
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.core.paginator import Paginator
from django.db.models import Q
import logging

from .models import Profil, MENUS
from .permissions import can_manage_users, get_user_permissions, check_comptable_restrictions
from .utils import user_is_admin

logger = logging.getLogger(__name__)

@login_required
@can_manage_users
def gestion_permissions(request):
    """
    Vue principale pour gérer les permissions des comptables
    """
    # Récupérer tous les comptables
    comptables = Profil.objects.filter(role='COMPTABLE').select_related('user', 'ecole')
    
    # Filtrage par école pour non-superusers
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if profil_user and profil_user.ecole_id:
            comptables = comptables.filter(ecole_id=profil_user.ecole_id)
        else:
            comptables = comptables.none()
    
    # Recherche
    search = request.GET.get('search', '').strip()
    if search:
        comptables = comptables.filter(
            Q(user__username__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(user__email__icontains=search)
        )
    
    # Pagination (ordonner pour éviter UnorderedObjectListWarning)
    try:
        comptables = comptables.order_by('user__username', 'id')
    except Exception:
        comptables = comptables.order_by('id')
    paginator = Paginator(comptables, 12)  # 12 comptables par page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'comptables': page_obj,
        'search': search,
        'total_comptables': comptables.count(),
        'MENUS': MENUS,
    }
    
    return render(request, 'utilisateurs/gestion_permissions.html', context)

@login_required
@can_manage_users
def update_permissions(request, comptable_id):
    """
    Mettre à jour les permissions d'un comptable spécifique
    """
    comptable = get_object_or_404(Profil, id=comptable_id, role='COMPTABLE')
    
    # Vérifier les droits d'accès par école
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if not (profil_user and profil_user.ecole_id == comptable.ecole_id):
            messages.error(request, "Vous ne pouvez pas modifier les permissions de ce comptable.")
            return redirect('utilisateurs:gestion_permissions')
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Récupérer les nouvelles permissions depuis le formulaire
                permissions = {
                    'peut_ajouter_paiements': 'peut_ajouter_paiements' in request.POST,
                    'peut_ajouter_depenses': 'peut_ajouter_depenses' in request.POST,
                    'peut_ajouter_enseignants': 'peut_ajouter_enseignants' in request.POST,
                    'peut_modifier_paiements': 'peut_modifier_paiements' in request.POST,
                    'peut_modifier_depenses': 'peut_modifier_depenses' in request.POST,
                    'peut_supprimer_paiements': 'peut_supprimer_paiements' in request.POST,
                    'peut_supprimer_depenses': 'peut_supprimer_depenses' in request.POST,
                    'peut_consulter_rapports': 'peut_consulter_rapports' in request.POST,
                }
                
                # Sauvegarder les anciennes permissions pour le log
                old_permissions = {
                    perm: getattr(comptable, perm, False) 
                    for perm in permissions.keys()
                }
                
                # Appliquer les nouvelles permissions
                for perm, value in permissions.items():
                    setattr(comptable, perm, value)
                # Menus autorisés (facultatif: si liste vide => pas de restriction)
                allowed = request.POST.getlist('allowed_menus')
                # Valider les clés contre MENUS
                valid_keys = {k for (k, _label) in MENUS}
                allowed = [k for k in allowed if k in valid_keys]
                comptable.allowed_menus = allowed
                
                comptable.save()
                
                # Log des changements
                changes = []
                for perm, new_value in permissions.items():
                    old_value = old_permissions.get(perm, False)
                    if old_value != new_value:
                        status = "activée" if new_value else "désactivée"
                        changes.append(f"{perm}: {status}")
                
                if changes:
                    logger.info(
                        f"Permissions modifiées pour {comptable.user.username} par {request.user.username}: "
                        f"{', '.join(changes)}"
                    )
                
                messages.success(
                    request,
                    f"Permissions de {comptable.user.get_full_name() or comptable.user.username} "
                    f"mises à jour avec succès !"
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des permissions: {str(e)}")
            messages.error(request, f"Erreur lors de la mise à jour : {str(e)}")
    
    return redirect('utilisateurs:gestion_permissions')

@login_required
@can_manage_users
def ajax_toggle_permission(request):
    """
    Vue AJAX pour basculer une permission spécifique
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'})
    
    try:
        comptable_id = request.POST.get('comptable_id')
        permission_name = request.POST.get('permission_name')
        new_value = request.POST.get('value') == 'true'
        
        comptable = get_object_or_404(Profil, id=comptable_id, role='COMPTABLE')
        
        # Vérifier les droits d'accès par école
        if not request.user.is_superuser:
            profil_user = getattr(request.user, 'profil', None)
            if not (profil_user and profil_user.ecole_id == comptable.ecole_id):
                return JsonResponse({'success': False, 'error': 'Accès refusé'})
        
        # Vérifier que la permission existe
        if not hasattr(comptable, permission_name):
            return JsonResponse({'success': False, 'error': 'Permission inconnue'})
        
        # Appliquer le changement
        old_value = getattr(comptable, permission_name)
        setattr(comptable, permission_name, new_value)
        comptable.save()
        
        # Log du changement
        status = "activée" if new_value else "désactivée"
        logger.info(
            f"Permission {permission_name} {status} pour {comptable.user.username} "
            f"par {request.user.username}"
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Permission {permission_name} {status}',
            'new_value': new_value
        })
        
    except Exception as e:
        logger.error(f"Erreur AJAX toggle permission: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
@can_manage_users
def bulk_update_permissions(request):
    """
    Mise à jour en masse des permissions
    """
    if request.method != 'POST':
        return redirect('utilisateurs:gestion_permissions')
    
    action = request.POST.get('action')
    comptable_ids = request.POST.getlist('comptable_ids')
    
    if not comptable_ids:
        messages.warning(request, "Aucun comptable sélectionné.")
        return redirect('utilisateurs:gestion_permissions')
    
    try:
        comptables = Profil.objects.filter(id__in=comptable_ids, role='COMPTABLE')
        
        # Vérifier les droits d'accès par école
        if not request.user.is_superuser:
            profil_user = getattr(request.user, 'profil', None)
            if profil_user and profil_user.ecole_id:
                comptables = comptables.filter(ecole_id=profil_user.ecole_id)
        
        with transaction.atomic():
            if action == 'restrict_all':
                # Tout restreindre
                permissions = {
                    'peut_ajouter_paiements': False,
                    'peut_ajouter_depenses': False,
                    'peut_ajouter_enseignants': False,
                    'peut_modifier_paiements': False,
                    'peut_modifier_depenses': False,
                    'peut_supprimer_paiements': False,
                    'peut_supprimer_depenses': False,
                    'peut_consulter_rapports': True,  # Garder la consultation
                }
                action_desc = "Toutes les permissions restreintes"
                
            elif action == 'allow_all':
                # Tout autoriser
                permissions = {
                    'peut_ajouter_paiements': True,
                    'peut_ajouter_depenses': True,
                    'peut_ajouter_enseignants': True,
                    'peut_modifier_paiements': True,
                    'peut_modifier_depenses': True,
                    'peut_supprimer_paiements': True,
                    'peut_supprimer_depenses': True,
                    'peut_consulter_rapports': True,
                }
                action_desc = "Toutes les permissions accordées"
                
            elif action == 'default_safe':
                # Configuration par défaut sécurisée
                permissions = {
                    'peut_ajouter_paiements': False,
                    'peut_ajouter_depenses': False,
                    'peut_ajouter_enseignants': False,
                    'peut_modifier_paiements': True,
                    'peut_modifier_depenses': True,
                    'peut_supprimer_paiements': False,
                    'peut_supprimer_depenses': False,
                    'peut_consulter_rapports': True,
                }
                action_desc = "Configuration par défaut appliquée"
            else:
                messages.error(request, "Action non reconnue.")
                return redirect('utilisateurs:gestion_permissions')
            
            # Appliquer les permissions
            updated_count = 0
            for comptable in comptables:
                for perm, value in permissions.items():
                    setattr(comptable, perm, value)
                comptable.save()
                updated_count += 1
            
            # Log de l'action
            logger.info(
                f"Mise à jour en masse par {request.user.username}: {action_desc} "
                f"pour {updated_count} comptable(s)"
            )
            
            messages.success(
                request,
                f"{action_desc} pour {updated_count} comptable(s) avec succès !"
            )
            
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour en masse: {str(e)}")
        messages.error(request, f"Erreur lors de la mise à jour : {str(e)}")
    
    return redirect('utilisateurs:gestion_permissions')

@login_required
def ajax_user_permissions(request):
    """
    Vue AJAX pour récupérer les permissions d'un utilisateur
    """
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifié'})
    
    permissions = get_user_permissions(request.user)
    restrictions = check_comptable_restrictions(request.user)
    
    return JsonResponse({
        'success': True,
        'permissions': permissions,
        'restrictions': restrictions,
        'user_role': getattr(request.user.profil, 'role', 'INCONNU') if hasattr(request.user, 'profil') else 'INCONNU'
    })

@login_required
@can_manage_users
def export_permissions_csv(request):
    """
    Exporter les permissions des comptables en CSV
    """
    import csv
    from django.http import HttpResponse
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="permissions_comptables.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Nom d\'utilisateur', 'Nom complet', 'Email', 'École',
        'Ajouter paiements', 'Ajouter dépenses', 'Ajouter enseignants',
        'Modifier paiements', 'Modifier dépenses',
        'Supprimer paiements', 'Supprimer dépenses',
        'Consulter rapports'
    ])
    
    comptables = Profil.objects.filter(role='COMPTABLE').select_related('user', 'ecole')
    
    # Filtrage par école pour non-superusers
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if profil_user and profil_user.ecole_id:
            comptables = comptables.filter(ecole_id=profil_user.ecole_id)
    
    for comptable in comptables:
        writer.writerow([
            comptable.user.username,
            comptable.user.get_full_name() or '',
            comptable.user.email or '',
            comptable.ecole.nom if comptable.ecole else '',
            'Oui' if getattr(comptable, 'peut_ajouter_paiements', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_ajouter_depenses', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_ajouter_enseignants', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_modifier_paiements', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_modifier_depenses', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_supprimer_paiements', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_supprimer_depenses', False) else 'Non',
            'Oui' if getattr(comptable, 'peut_consulter_rapports', False) else 'Non',
        ])
    
    return response
