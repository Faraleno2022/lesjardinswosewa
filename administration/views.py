from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.apps import apps
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import secrets
import string
from typing import Optional

from .models import SystemLog, MaintenanceMode
from eleves.models import Eleve, Classe, Ecole, GrilleTarifaire
from paiements.models import Paiement
from utilisateurs.models import Profil

logger = logging.getLogger(__name__)


def _current_school_year():
    try:
        today = timezone.now().date()
    except Exception:
        from datetime import date as _d
        today = _d.today()
    try:
        return f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}"
    except Exception:
        return "2025-2026"


def _bootstrap_ecole_structure(ecole: 'Ecole', created_by: Optional['User'] = None):
    """Crée automatiquement une structure minimale pour une école validée:
    - Classes par défaut (affichages standards pour chaque niveau)
    - Grilles tarifaires (montants à 0 par défaut)
    - Lie le profil utilisateur (si présent) à l'école

    Idempotent: ne recrée pas si existent déjà.
    """
    try:
        # Lier profil.ecole si vide
        if created_by and hasattr(created_by, 'profil'):
            try:
                if getattr(created_by.profil, 'ecole', None) is None:
                    created_by.profil.ecole = ecole
                    created_by.profil.save(update_fields=['ecole'])
            except Exception:
                pass

        # Ne pas dupliquer si classes déjà présentes
        if Classe.objects.filter(ecole=ecole).exists():
            return

        annee = _current_school_year()

        # Créer une classe par niveau avec le libellé lisible comme nom
        niveaux = list(Classe.NIVEAUX_CHOICES)
        classes_to_create = []
        for code, label in niveaux:
            try:
                classes_to_create.append(Classe(
                    ecole=ecole,
                    nom=label,  # nom lisible
                    niveau=code,
                    annee_scolaire=annee,
                    capacite_max=30,
                ))
            except Exception:
                continue
        if classes_to_create:
            Classe.objects.bulk_create(classes_to_create, ignore_conflicts=True)

        # Créer grilles tarifaires à 0 par niveau si non existantes
        for code, _label in niveaux:
            try:
                GrilleTarifaire.objects.get_or_create(
                    ecole=ecole,
                    niveau=code,
                    annee_scolaire=annee,
                    defaults=dict(
                        frais_inscription=0,
                        tranche_1=0,
                        tranche_2=0,
                        tranche_3=0,
                    )
                )
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Bootstrap école échoué (ecole_id={getattr(ecole, 'id', None)}): {e}")


def is_super_admin(user):
    """Vérifie si l'utilisateur est un super administrateur"""
    return user.is_superuser and user.is_staff


def log_admin_action(action, description, user=None, ip_address=None, details=None):
    """Enregistre une action administrative"""
    SystemLog.objects.create(
        action=action,
        description=description,
        user=user,
        ip_address=ip_address,
        details=details or {}
    )


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def dashboard(request):
    """Tableau de bord d'administration optimisé avec cache intelligent"""
    from ecole_moderne.performance_config import get_cached_or_set, CACHE_TTL, CACHE_KEYS
    from django.db.models import Count, Case, When, Q
    
    # Cache des statistiques principales
    def get_dashboard_stats():
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Agrégation optimisée en une seule requête
        return {
            'total_users': User.objects.count(),
            'total_eleves': Eleve.objects.count(),
            'total_ecoles': Ecole.objects.count(),
            'total_paiements': Paiement.objects.count(),
            'users_actifs': User.objects.filter(is_active=True).count(),
            'paiements_mois': Paiement.objects.filter(date_paiement__gte=month_start).count(),
        }
    
    cache_key = CACHE_KEYS['stats_dashboard'].format(request.user.id)
    stats = get_cached_or_set(cache_key, get_dashboard_stats, CACHE_TTL['stats_dashboard'])
    
    # Cache des logs récents
    def get_recent_logs():
        return list(SystemLog.objects.select_related('user').order_by('-timestamp')[:10])
    
    logs_cache_key = f'recent_logs_{request.user.id}'
    recent_logs = get_cached_or_set(logs_cache_key, get_recent_logs, 60)  # 1 minute
    
    # Cache du mode maintenance
    def get_maintenance_mode():
        return MaintenanceMode.objects.first()
    
    maintenance_cache_key = 'maintenance_mode_global'
    maintenance_mode = get_cached_or_set(maintenance_cache_key, get_maintenance_mode, 300)  # 5 minutes
    
    # Cache des écoles en attente
    def get_pending_schools_data():
        pending_schools = list(Ecole.objects.filter(etat='EN_ATTENTE').order_by('-date_creation')[:10])
        pending_count = Ecole.objects.filter(etat='EN_ATTENTE').count()
        return {'schools': pending_schools, 'count': pending_count}
    
    pending_cache_key = 'pending_schools_data'
    pending_data = get_cached_or_set(pending_cache_key, get_pending_schools_data, 180)  # 3 minutes
    
    context = {
        'stats': stats,
        'recent_logs': recent_logs,
        'maintenance_mode': maintenance_mode,
        'pending_schools': pending_data['schools'],
        'pending_count': pending_data['count'],
        'titre_page': 'Administration - Tableau de bord'
    }
    
    return render(request, 'administration/dashboard.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def users_management(request):
    """Gestion des utilisateurs"""
    
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')
    pending_only = (request.GET.get('pending') or '') == '1'
    
    users = User.objects.select_related('profil').all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    if role_filter:
        users = users.filter(profil__role=role_filter)
    
    # Filtre: uniquement les comptes en attente (inactifs ou non validés)
    if pending_only:
        users = users.filter(
            Q(is_active=False) | Q(profil__is_validated=False)
        ).exclude(is_superuser=True)
    
    # Pagination (ajouter un order_by explicite pour éviter l'avertissement UnorderedObjectListWarning)
    users = users.order_by('username', 'id')
    paginator = Paginator(users, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Rôles disponibles pour le filtre
    roles = Profil.objects.values_list('role', flat=True).distinct()
    
    # Demandes en attente
    pending_users_qs = User.objects.select_related('profil').filter(
        Q(is_active=False) | Q(profil__is_validated=False)
    ).exclude(is_superuser=True).order_by('-date_joined')
    pending_schools_qs = Ecole.objects.filter(etat='EN_ATTENTE').select_related('created_by').order_by('-date_creation')

    context = {
        'page_obj': page_obj,
        'search_query': search_query,
        'role_filter': role_filter,
        'pending_only': '1' if pending_only else '',
        'roles': roles,
        'pending_users': pending_users_qs[:10],
        'pending_users_count': pending_users_qs.count(),
        'pending_schools': pending_schools_qs[:10],
        'pending_schools_count': pending_schools_qs.count(),
        'titre_page': 'Gestion des utilisateurs'
    }
    
    return render(request, 'administration/users_management.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def system_stats(request):
    """Statistiques système détaillées"""
    
    # Statistiques par école
    ecoles_stats = []
    for ecole in Ecole.objects.all():
        ecoles_stats.append({
            'ecole': ecole,
            'eleves': Eleve.objects.filter(classe__ecole=ecole).count(),
            'classes': Classe.objects.filter(ecole=ecole).count(),
            'paiements': Paiement.objects.filter(eleve__classe__ecole=ecole).count(),
        })
    
    # Statistiques temporelles
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    month_ago = today - timedelta(days=30)
    
    temporal_stats = {
        'paiements_semaine': Paiement.objects.filter(date_paiement__gte=week_ago).count(),
        'paiements_mois': Paiement.objects.filter(date_paiement__gte=month_ago).count(),
        'nouveaux_eleves_mois': Eleve.objects.filter(date_inscription__gte=month_ago).count(),
        'connexions_semaine': SystemLog.objects.filter(
            action='LOGIN',
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    context = {
        'ecoles_stats': ecoles_stats,
        'temporal_stats': temporal_stats,
        'titre_page': 'Statistiques système'
    }
    
    return render(request, 'administration/system_stats.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def system_logs(request):
    """Consultation des logs système"""
    
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    date_filter = request.GET.get('date', '')
    
    logs = SystemLog.objects.select_related('user').all()
    
    if action_filter:
        logs = logs.filter(action=action_filter)
    
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)
    
    if date_filter:
        try:
            filter_date = datetime.strptime(date_filter, '%Y-%m-%d').date()
            logs = logs.filter(timestamp__date=filter_date)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Actions disponibles pour le filtre
    actions = SystemLog.ACTION_CHOICES
    
    context = {
        'page_obj': page_obj,
        'action_filter': action_filter,
        'user_filter': user_filter,
        'date_filter': date_filter,
        'actions': actions,
        'titre_page': 'Logs système'
    }
    
    return render(request, 'administration/system_logs.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def toggle_maintenance(request):
    """Active/désactive le mode maintenance"""
    
    maintenance_mode, created = MaintenanceMode.objects.get_or_create(
        defaults={'is_active': False}
    )
    
    action = request.POST.get('action')
    
    if action == 'activate':
        maintenance_mode.is_active = True
        maintenance_mode.activated_by = request.user
        maintenance_mode.activated_at = timezone.now()
        message = request.POST.get('message', maintenance_mode.message)
        maintenance_mode.message = message
        maintenance_mode.save()
        
        log_admin_action(
            'RESET',
            'Mode maintenance activé',
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={'message': message}
        )
        
        messages.success(request, 'Mode maintenance activé.')
        
    elif action == 'deactivate':
        maintenance_mode.is_active = False
        maintenance_mode.save()
        
        log_admin_action(
            'RESET',
            'Mode maintenance désactivé',
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, 'Mode maintenance désactivé.')
    
    return redirect('administration:dashboard')


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def clear_old_logs(request):
    """Supprime les anciens logs (plus de 90 jours)"""
    
    cutoff_date = timezone.now() - timedelta(days=90)
    deleted_count = SystemLog.objects.filter(timestamp__lt=cutoff_date).count()
    SystemLog.objects.filter(timestamp__lt=cutoff_date).delete()
    
    log_admin_action(
        'DELETE',
        f'Nettoyage des logs anciens: {deleted_count} entrées supprimées',
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'deleted_count': deleted_count}
    )
    
    messages.success(request, f'{deleted_count} anciens logs supprimés.')
    return redirect('administration:system_logs')


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def user_detail(request, user_id):
    """Détail d'un utilisateur"""
    
    user = get_object_or_404(User, pk=user_id)
    
    # Logs de cet utilisateur
    user_logs = SystemLog.objects.filter(user=user)[:20]
    
    # Statistiques si c'est un utilisateur avec profil
    user_stats = {}
    if hasattr(user, 'profil') and user.profil.ecole:
        ecole = user.profil.ecole
        user_stats = {
            'ecole': ecole,
            'eleves_ecole': Eleve.objects.filter(classe__ecole=ecole).count(),
            'paiements_traites': Paiement.objects.filter(
                # Supposons qu'on ait un champ created_by ou similar
                date_paiement__gte=timezone.now() - timedelta(days=30)
            ).count(),
        }
    
    context = {
        'user_detail': user,
        'user_logs': user_logs,
        'user_stats': user_stats,
        'titre_page': f'Utilisateur - {user.get_full_name() or user.username}'
    }
    
    return render(request, 'administration/user_detail.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
def corbeille_list(request):
    """Affiche la corbeille avec les éléments supprimés définitivement"""
    
    # Récupérer les suppressions définitives
    suppressions = SystemLog.objects.filter(
        action='SUPPRESSION_DEFINITIVE'
    ).select_related('user').order_by('-timestamp')
    
    # Pagination
    paginator = Paginator(suppressions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    stats = {
        'total_suppressions': suppressions.count(),
        'suppressions_aujourd_hui': suppressions.filter(
            timestamp__date=timezone.now().date()
        ).count(),
        'suppressions_cette_semaine': suppressions.filter(
            timestamp__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }
    
    context = {
        'suppressions': page_obj,
        'stats': stats,
        'titre_page': 'Corbeille - Éléments supprimés'
    }
    
    return render(request, 'administration/corbeille.html', context)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def restaurer_element(request, log_id):
    """Restaure un élément supprimé depuis la corbeille"""
    
    try:
        # Récupérer le log de suppression
        log_suppression = get_object_or_404(
            SystemLog, 
            id=log_id, 
            action='SUPPRESSION_DEFINITIVE'
        )
        
        # Vérifier que l'élément n'a pas déjà été restauré
        if SystemLog.objects.filter(
            action='RESTORE',
            details__original_log_id=log_id
        ).exists():
            return JsonResponse({
                'success': False, 
                'error': 'Cet élément a déjà été restauré.'
            })
        
        # Extraire les détails de la suppression
        details = log_suppression.details
        
        if not details or 'eleve_id' not in details:
            return JsonResponse({
                'success': False, 
                'error': 'Données de restauration incomplètes.'
            })
        
        with transaction.atomic():
            # Restaurer l'élève
            eleve_data = {
                'matricule': details.get('matricule'),
                'nom': details.get('nom_complet', '').split(' ')[-1],
                'prenom': ' '.join(details.get('nom_complet', '').split(' ')[:-1]),
                'statut': 'ACTIF',  # Restaurer comme actif
            }
            
            # Trouver la classe (si elle existe encore)
            classe_nom = details.get('classe', '')
            classe = None
            if classe_nom:
                try:
                    classe = Classe.objects.get(nom__icontains=classe_nom.split(' - ')[0])
                except Classe.DoesNotExist:
                    pass
            
            if not classe:
                return JsonResponse({
                    'success': False, 
                    'error': f'Impossible de restaurer: la classe "{classe_nom}" n\'existe plus.'
                })
            
            # Créer le nouvel élève restauré
            from eleves.models import Eleve
            eleve_restaure = Eleve.objects.create(
                matricule=eleve_data['matricule'] + '_RESTAURE',  # Éviter les doublons
                nom=eleve_data['nom'],
                prenom=eleve_data['prenom'],
                classe=classe,
                statut=eleve_data['statut']
            )
            
            # Enregistrer la restauration
            SystemLog.objects.create(
                action='RESTORE',
                description=f"Restauration de l'élève {details.get('nom_complet')} (nouveau ID: {eleve_restaure.id})",
                user=request.user,
                ip_address=request.META.get('REMOTE_ADDR', ''),
                details={
                    'original_log_id': log_id,
                    'original_eleve_id': details.get('eleve_id'),
                    'new_eleve_id': eleve_restaure.id,
                    'matricule_original': details.get('matricule'),
                    'matricule_restaure': eleve_restaure.matricule,
                    'classe': str(classe),
                    'paiements_perdus': len(details.get('paiements_supprimes', [])),
                    'user_agent': request.META.get('HTTP_USER_AGENT', '')
                }
            )
            
            return JsonResponse({
                'success': True,
                'message': f'Élève restauré avec succès. Nouveau matricule: {eleve_restaure.matricule}',
                'new_eleve_id': eleve_restaure.id,
                'new_matricule': eleve_restaure.matricule
            })
            
    except Exception as e:
        logger.error(f"Erreur lors de la restauration: {e}")
        return JsonResponse({
            'success': False, 
            'error': f'Erreur lors de la restauration: {str(e)}'
        })


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def valider_ecole(request, ecole_id):
    """Valide une école en attente et l'active (etat -> VALIDE)."""
    ecole = get_object_or_404(Ecole, pk=ecole_id)
    previous = ecole.etat
    ecole.etat = 'VALIDE'
    ecole.save(update_fields=['etat'])
    # Bootstrap structure (classes + grilles) et lier profil utilisateur
    try:
        _bootstrap_ecole_structure(ecole, created_by=getattr(ecole, 'created_by', None))
    except Exception:
        pass
    # Log
    log_admin_action(
        'RESET',
        f"Validation de l'école: {ecole.nom}",
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'ecole_id': ecole.id, 'previous_state': previous, 'new_state': 'VALIDE'}
    )
    messages.success(request, f"École '{ecole.nom}' validée et activée.")
    return redirect('administration:dashboard')


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def rejeter_ecole(request, ecole_id):
    """Rejette une école (etat -> REJETE)."""
    ecole = get_object_or_404(Ecole, pk=ecole_id)
    previous = ecole.etat
    ecole.etat = 'REJETE'
    ecole.save(update_fields=['etat'])
    # Log
    log_admin_action(
        'RESET',
        f"Rejet de l'école: {ecole.nom}",
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'ecole_id': ecole.id, 'previous_state': previous, 'new_state': 'REJETE'}
    )
    messages.info(request, f"École '{ecole.nom}' rejetée.")
    return redirect('administration:dashboard')


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def user_toggle_active(request, user_id):
    """Active/Désactive un utilisateur."""
    target = get_object_or_404(User, pk=user_id)
    target.is_active = not target.is_active
    target.save(update_fields=["is_active"])
    state = 'activé' if target.is_active else 'désactivé'
    log_admin_action(
        'RESET',
        f"Utilisateur {target.username} {state}",
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'user_id': target.id, 'new_is_active': target.is_active}
    )
    messages.success(request, f"Utilisateur '{target.username}' {state}.")
    return redirect('administration:user_detail', user_id=target.id)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def user_toggle_staff(request, user_id):
    """Bascule le statut staff (permissions d'accès admin Django)."""
    target = get_object_or_404(User, pk=user_id)
    target.is_staff = not target.is_staff
    target.save(update_fields=["is_staff"])
    state = 'désormais STAFF' if target.is_staff else 'n\'est plus STAFF'
    log_admin_action(
        'RESET',
        f"Changement de statut staff pour {target.username}: {state}",
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'user_id': target.id, 'new_is_staff': target.is_staff}
    )
    messages.info(request, f"{target.username} {state}.")
    return redirect('administration:user_detail', user_id=target.id)


def _generate_temp_password(length: int = 12) -> str:
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def user_reset_password(request, user_id):
    """Réinitialise le mot de passe en un mot de passe temporaire aléatoire."""
    target = get_object_or_404(User, pk=user_id)
    temp_pwd = _generate_temp_password()
    target.set_password(temp_pwd)
    target.save(update_fields=[])
    log_admin_action(
        'RESET',
        f"Réinitialisation du mot de passe pour {target.username}",
        user=request.user,
        ip_address=request.META.get('REMOTE_ADDR'),
        details={'user_id': target.id}
    )
    messages.warning(request, f"Mot de passe temporaire pour '{target.username}': {temp_pwd}")
    return redirect('administration:user_detail', user_id=target.id)


@login_required
@user_passes_test(is_super_admin, login_url='admin:login')
@require_POST
@csrf_protect
def user_activate_and_validate(request, user_id):
    """Active un utilisateur et valide ses écoles en attente (etat -> VALIDE)."""
    target = get_object_or_404(User, pk=user_id)
    activated = False
    validated_count = 0
    previous_active = target.is_active
    with transaction.atomic():
        if not target.is_active:
            target.is_active = True
            target.save(update_fields=["is_active"])
            activated = True
        # Valider les écoles en attente créées par cet utilisateur
        pending = Ecole.objects.filter(created_by=target, etat='EN_ATTENTE')
        validated = list(pending)
        validated_count = len(validated)
        if validated_count:
            Ecole.objects.filter(id__in=[e.id for e in validated]).update(etat='VALIDE')
            # Bootstrap pour chaque école validée
            for ecole in validated:
                try:
                    ecole.etat = 'VALIDE'
                    _bootstrap_ecole_structure(ecole, created_by=target)
                except Exception:
                    continue
    # Logs
    if activated:
        log_admin_action(
            'RESET',
            f"Activation de l'utilisateur {target.username}",
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={'user_id': target.id, 'previous_active': previous_active, 'new_active': True}
        )
    if validated_count:
        log_admin_action(
            'RESET',
            f"Validation de {validated_count} école(s) pour {target.username}",
            user=request.user,
            ip_address=request.META.get('REMOTE_ADDR'),
            details={'user_id': target.id, 'validated_count': validated_count}
        )
    # Notifications par email
    try:
        if (activated or validated_count) and target.email:
            subject = "Myschool - Votre compte et/ou école ont été validés"
            parts = []
            if activated:
                parts.append("Votre compte a été activé.")
            if validated_count:
                parts.append(f"{validated_count} école(s) associée(s) ont été validée(s).")
            body = (
                "Bonjour,\n\n" +
                " ".join(parts) + "\n\n" +
                "Vous pouvez maintenant vous connecter à votre espace: "
                f"{getattr(settings, 'SITE_BASE_URL', 'https://www.myschoolgn.space')}/utilisateurs/login/\n\n"
                "Cordialement,\nL'équipe Myschool"
            )
            try:
                send_mail(
                    subject,
                    body,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@myschoolgn.space'),
                    [target.email],
                    fail_silently=True,
                )
            except Exception:
                pass
    except Exception:
        pass

    # Messages
    if activated and validated_count:
        messages.success(request, f"Utilisateur activé et {validated_count} école(s) validée(s).")
    elif activated:
        messages.success(request, "Utilisateur activé.")
    elif validated_count:
        messages.success(request, f"{validated_count} école(s) validée(s).")
    else:
        messages.info(request, "Aucun changement à appliquer.")
    return redirect('administration:user_detail', user_id=target.id)
