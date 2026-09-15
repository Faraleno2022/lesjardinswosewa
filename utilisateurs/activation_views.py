# -*- coding: utf-8 -*-
"""
MySchoolGN - Gestion des comptes utilisateurs
==============================================
Auteur : GS Hadja Kanfing Dian
"""

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods

User = get_user_model()


# ─── Page principale de gestion des comptes ──────────────────────────────────
@login_required
def activation_page(request):
    """Page historique ``activation`` devenue la gestion des comptes admin."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé à l'administrateur principal.")
        return redirect('/')

    context = {
        'users': User.objects.all().order_by('-is_superuser', 'username'),
        'page_title': 'Gestion des comptes',
    }
    return render(request, 'utilisateurs/activation.html', context)


# ─── Création de compte utilisateur ──────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def creer_compte(request):
    """Crée un nouvel utilisateur (admin ou comptable)."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé à l'administrateur principal.")
        return redirect('utilisateurs:activation')

    username   = request.POST.get('username', '').strip()
    password   = request.POST.get('password', '').strip()
    password2  = request.POST.get('password2', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name  = request.POST.get('last_name', '').strip()
    email      = request.POST.get('email', '').strip()
    role       = request.POST.get('role', 'user')

    # Validations
    if not username or not password:
        messages.error(request, "Nom d'utilisateur et mot de passe sont obligatoires.")
        return redirect('utilisateurs:activation')

    if password != password2:
        messages.error(request, "Les mots de passe ne correspondent pas.")
        return redirect('utilisateurs:activation')

    if len(password) < 6:
        messages.error(request, "Le mot de passe doit contenir au moins 6 caractères.")
        return redirect('utilisateurs:activation')

    if User.objects.filter(username=username).exists():
        messages.error(request, f"L'utilisateur « {username} » existe déjà.")
        return redirect('utilisateurs:activation')

    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
        if role == 'admin':
            user.is_staff = True
            user.is_superuser = True
            user.save()
            messages.success(request,
                f"✓ Compte administrateur « {username} » créé avec succès.")
        else:
            user.is_staff = True
            user.save()
            messages.success(request,
                f"✓ Compte utilisateur « {username} » créé avec succès.")
    except Exception as e:
        messages.error(request, f"Erreur lors de la création : {e}")

    return redirect('utilisateurs:activation')


# ─── Changer mot de passe admin ───────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def changer_mdp_admin(request):
    """Change le mot de passe du compte admin principal."""
    if not request.user.is_superuser:
        messages.error(request, "Accès réservé à l'administrateur principal.")
        return redirect('utilisateurs:activation')

    old_pass  = request.POST.get('old_password', '')
    new_pass  = request.POST.get('new_password', '')
    new_pass2 = request.POST.get('new_password2', '')

    if not request.user.check_password(old_pass):
        messages.error(request, "Mot de passe actuel incorrect.")
        return redirect('utilisateurs:activation')

    if new_pass != new_pass2:
        messages.error(request, "Les nouveaux mots de passe ne correspondent pas.")
        return redirect('utilisateurs:activation')

    if len(new_pass) < 6:
        messages.error(request, "Le nouveau mot de passe doit contenir au moins 6 caractères.")
        return redirect('utilisateurs:activation')

    request.user.set_password(new_pass)
    request.user.save()
    update_session_auth_hash(request, request.user)
    messages.success(request, "✓ Mot de passe modifié avec succès.")
    return redirect('utilisateurs:activation')


# ─── Supprimer un utilisateur ─────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def supprimer_compte(request, user_id):
    """Supprime un compte utilisateur (sauf le superuser courant)."""
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé.")
        return redirect('utilisateurs:activation')

    if user_id == request.user.id:
        messages.error(request, "Vous ne pouvez pas supprimer votre propre compte.")
        return redirect('utilisateurs:activation')

    try:
        user = User.objects.get(id=user_id)
        username = user.username
        user.delete()
        messages.success(request, f"✓ Compte « {username} » supprimé.")
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")

    return redirect('utilisateurs:activation')


@login_required
def toggle_lecture_seule(request, user_id):
    """Active/désactive le mode lecture seule d'un utilisateur (superuser only)."""
    from .models import Profil
    if not request.user.is_superuser:
        messages.error(request, "Accès refusé.")
        return redirect('utilisateurs:activation')

    if user_id == request.user.id:
        messages.error(request, "Vous ne pouvez pas vous mettre vous-même en lecture seule.")
        return redirect('utilisateurs:activation')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, "Utilisateur introuvable.")
        return redirect('utilisateurs:activation')

    if user.is_superuser:
        messages.error(request, "Un superutilisateur ne peut pas être mis en lecture seule.")
        return redirect('utilisateurs:activation')

    profil, _ = Profil.objects.get_or_create(
        user=user, defaults={'role': 'SECRETAIRE', 'telephone': '+224000000000'})
    profil.lecture_seule = not profil.lecture_seule
    profil.save(update_fields=['lecture_seule'])

    if profil.lecture_seule:
        messages.success(request, f"🔒 « {user.username} » est maintenant en LECTURE SEULE (consultation uniquement).")
    else:
        messages.success(request, f"🔓 « {user.username} » peut de nouveau effectuer des actions.")
    return redirect('utilisateurs:activation')
