from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import ComptableCreationForm
from .models import Profil
from eleves.models import Ecole


def _est_admin(user):
    """Vrai si superuser ou profil ADMIN avec droit de gestion utilisateurs."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profil = getattr(user, 'profil', None)
    return bool(profil and profil.role == 'ADMIN' and profil.peut_gerer_utilisateurs)


@login_required
@user_passes_test(_est_admin)
def comptable_create_view(request):
    """Création d'un compte Comptable (User + Profil) via formulaire dédié."""
    # Si ce n'est pas un superuser, il doit avoir une école définie
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if not (profil_user and profil_user.ecole_id):
            # Page dédiée d'accès refusé (403)
            return render(request, 'utilisateurs/acces_refuse_ecole.html', status=403)
    if request.method == 'POST':
        form = ComptableCreationForm(request.POST, request=request)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"Compte comptable créé avec succès: {user.username}"
            )
            return redirect('home')
        else:
            messages.error(request, "Veuillez corriger les erreurs du formulaire.")
    else:
        form = ComptableCreationForm(request=request)

    return render(request, 'utilisateurs/comptable_form.html', {
        'form': form,
        'title': "Créer un comptable",
    })


@login_required
@user_passes_test(_est_admin)
def comptable_list_view(request):
    """Liste paginée des comptes Comptables, filtrable par école et recherche."""
    qs = Profil.objects.select_related('user', 'ecole').filter(role='COMPTABLE')

    ecole_id = request.GET.get('ecole')
    q = request.GET.get('q')
    # Isolation par école pour non-superadmins
    if not request.user.is_superuser:
        profil_user = getattr(request.user, 'profil', None)
        if profil_user and profil_user.ecole_id:
            qs = qs.filter(ecole_id=profil_user.ecole_id)
            # Forcer le filtre d'école à celle de l'utilisateur
            ecole_id = str(profil_user.ecole_id)
        else:
            # Pas d'école: aucun résultat
            qs = qs.none()

    if ecole_id:
        qs = qs.filter(ecole_id=ecole_id)
    if q:
        qs = qs.filter(
            Q(user__username__icontains=q)
            | Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__email__icontains=q)
            | Q(telephone__icontains=q)
        )

    paginator = Paginator(qs.order_by('user__username'), 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Restreindre la liste des écoles à celle de l'utilisateur si non superuser
    if request.user.is_superuser:
        ecoles = Ecole.objects.all().order_by('nom') if hasattr(Ecole, 'nom') else Ecole.objects.all()
    else:
        profil_user = getattr(request.user, 'profil', None)
        base = Ecole.objects.all()
        base = base.order_by('nom') if hasattr(Ecole, 'nom') else base
        if profil_user and profil_user.ecole_id:
            ecoles = base.filter(pk=profil_user.ecole_id)
        else:
            ecoles = base.none()

    return render(request, 'utilisateurs/comptable_list.html', {
        'page_obj': page_obj,
        'ecoles': ecoles,
        'filtre_ecole': ecole_id or '',
        'query': q or '',
        'title': "Comptables",
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profil') and u.profil.role == 'ADMIN'))
def comptes_en_attente_view(request):
    """Liste des comptes utilisateurs en attente de validation administrative."""
    from django.contrib.auth.models import User
    from eleves.models import Ecole
    
    # Utilisateurs avec profil non validé ou sans profil mais inactifs
    qs = User.objects.select_related('profil').filter(
        Q(is_active=False) | Q(profil__is_validated=False)
    ).exclude(is_superuser=True).order_by('-date_joined')
    
    # Filtrage par recherche
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q)
        )
    
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))
    
    # Récupérer les écoles créées par ces utilisateurs
    ecoles_en_attente = Ecole.objects.filter(
        created_by__in=qs,
        etat='EN_ATTENTE'
    ).select_related('created_by')
    
    return render(request, 'utilisateurs/comptes_en_attente.html', {
        'page_obj': page_obj,
        'ecoles_en_attente': ecoles_en_attente,
        'query': q,
        'title': "Comptes en attente de validation",
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profil') and u.profil.role == 'ADMIN'))
def valider_compte_view(request, user_id):
    """Valide un compte utilisateur et son école associée."""
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404
    from eleves.models import Ecole
    from eleves.utils import valider_compte_utilisateur
    from django.core.mail import send_mail
    from django.conf import settings
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        telephone = request.POST.get('telephone', '').strip()
        adresse = request.POST.get('adresse', '').strip()
        valider_ecole = request.POST.get('valider_ecole') == 'on'
        
        try:
            # Trouver l'école créée par cet utilisateur
            ecole = None
            if valider_ecole:
                try:
                    ecole = Ecole.objects.get(created_by=user, etat='EN_ATTENTE')
                    # Respecter les choix du modèle: BROUILLON, EN_ATTENTE, VALIDE, REJETE
                    ecole.etat = 'VALIDE'
                    ecole.save()
                except Ecole.DoesNotExist:
                    pass
            
            # Valider le compte utilisateur
            profil = valider_compte_utilisateur(user, ecole, telephone, adresse)
            
            # Envoyer un email de confirmation si possible
            try:
                if user.email:
                    subject = "Myschool - Compte validé"
                    body = f"""Bonjour {user.get_full_name() or user.username},

Votre compte Myschool a été validé par un administrateur.

Vous pouvez maintenant vous connecter avec vos identifiants :
- Nom d'utilisateur : {user.username}
- Mot de passe : celui que vous avez défini lors de l'inscription

"""
                    if ecole:
                        body += f"Votre école '{ecole.nom}' a également été validée et activée.\n\n"
                    
                    body += """Accédez à votre espace : https://myschoolgn.space/

Cordialement,
L'équipe Myschool"""
                    
                    send_mail(
                        subject,
                        body,
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@myschoolgn.space'),
                        [user.email],
                        fail_silently=True,
                    )
            except Exception:
                pass
            
            messages.success(request, f"Compte de {user.username} validé avec succès.")
            if ecole:
                messages.info(request, f"École '{ecole.nom}' également validée et activée.")
            
            return redirect('utilisateurs:comptes_en_attente')
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la validation : {e}")
    
    # Récupérer l'école associée s'il y en a une
    ecole_associee = None
    try:
        # Préfetch des relations pour l'affichage (classes et grilles)
        ecole_associee = (
            Ecole.objects
            .filter(created_by=user, etat='EN_ATTENTE')
            .prefetch_related('classes', 'grilles_tarifaires')
            .first()
        )
    except Exception:
        ecole_associee = None
    
    return render(request, 'utilisateurs/valider_compte.html', {
        'user_to_validate': user,
        'ecole_associee': ecole_associee,
        'title': f"Valider le compte de {user.username}",
    })


@login_required
@user_passes_test(lambda u: u.is_superuser or (hasattr(u, 'profil') and u.profil.role == 'ADMIN'))
def rejeter_compte_view(request, user_id):
    """Rejette un compte utilisateur et supprime son école associée."""
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404
    from eleves.models import Ecole
    from django.core.mail import send_mail
    from django.conf import settings
    
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        raison = request.POST.get('raison', '').strip()
        
        try:
            # Supprimer l'école associée si elle existe
            ecole_supprimee = None
            try:
                ecole = Ecole.objects.get(created_by=user, etat='EN_ATTENTE')
                ecole_supprimee = ecole.nom
                ecole.delete()
            except Ecole.DoesNotExist:
                pass
            
            # Envoyer un email de notification si possible
            try:
                if user.email:
                    subject = "Myschool - Demande rejetée"
                    body = f"""Bonjour {user.get_full_name() or user.username},

Nous regrettons de vous informer que votre demande de création de compte Myschool a été rejetée.

"""
                    if raison:
                        body += f"Raison : {raison}\n\n"
                    
                    if ecole_supprimee:
                        body += f"L'école '{ecole_supprimee}' associée à votre demande a été supprimée.\n\n"
                    
                    body += """Vous pouvez soumettre une nouvelle demande en corrigeant les éléments mentionnés.

Cordialement,
L'équipe Myschool"""
                    
                    send_mail(
                        subject,
                        body,
                        getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@myschoolgn.space'),
                        [user.email],
                        fail_silently=True,
                    )
            except Exception:
                pass
            
            # Supprimer le compte utilisateur
            username = user.username
            user.delete()
            
            messages.success(request, f"Compte de {username} rejeté et supprimé.")
            if ecole_supprimee:
                messages.info(request, f"École '{ecole_supprimee}' également supprimée.")
            
            return redirect('utilisateurs:comptes_en_attente')
            
        except Exception as e:
            messages.error(request, f"Erreur lors du rejet : {e}")
    
    # Récupérer l'école associée s'il y en a une
    ecole_associee = None
    try:
        ecole_associee = Ecole.objects.get(created_by=user, etat='EN_ATTENTE')
    except Ecole.DoesNotExist:
        pass
    
    return render(request, 'utilisateurs/rejeter_compte.html', {
        'user_to_reject': user,
        'ecole_associee': ecole_associee,
        'title': f"Rejeter le compte de {user.username}",
    })
