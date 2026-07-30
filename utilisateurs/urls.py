from django.urls import path
from django.contrib.auth import views as auth_views
from .views import comptable_create_view, comptable_list_view, comptes_en_attente_view, valider_compte_view, rejeter_compte_view
from .activation_views import (
    activation_page, activer_licence, creer_compte,
    changer_mdp_admin, supprimer_compte, toggle_lecture_seule,
)
from .security_views import (
    secure_login, secure_logout, SecurePasswordChangeView, verify_phone,
    security_dashboard, security_lockdown, security_unlock,
    password_reset_info,
    security_clear_login_lock,
    admin_unlock,
    admin_verify,
)
from .permission_views import (
    gestion_permissions, update_permissions, ajax_toggle_permission,
    bulk_update_permissions, ajax_user_permissions, export_permissions_csv
)

app_name = 'utilisateurs'

urlpatterns = [
    # Auth sécurisé
    path('login/', secure_login, name='login'),
    path('logout/', secure_logout, name='logout'),
    path('password/change/', SecurePasswordChangeView.as_view(), name='password_change'),
    path('password/reset/', password_reset_info, name='password_reset_info'),
    path('admin/verify/', admin_verify, name='admin_verify'),
    path('verify-phone/', verify_phone, name='verify_phone'),
    path('comptables/ajouter/', comptable_create_view, name='comptable_create'),
    path('comptables/', comptable_list_view, name='comptable_list'),

    # Validation des comptes
    path('comptes-en-attente/', comptes_en_attente_view, name='comptes_en_attente'),
    path('valider-compte/<int:user_id>/', valider_compte_view, name='valider_compte'),
    path('rejeter-compte/<int:user_id>/', rejeter_compte_view, name='rejeter_compte'),

    # ── Activation licence & gestion comptes ─────────────────────────────────
    path('activation/', activation_page, name='activation'),
    path('activation/activer-licence/', activer_licence, name='activer_licence'),
    path('activation/creer-compte/', creer_compte, name='creer_compte'),
    path('activation/changer-mdp/', changer_mdp_admin, name='changer_mdp_admin'),
    path('activation/supprimer-compte/<int:user_id>/', supprimer_compte, name='supprimer_compte'),
    path('activation/lecture-seule/<int:user_id>/', toggle_lecture_seule, name='toggle_lecture_seule'),

    # Gestion des permissions
    path('permissions/', gestion_permissions, name='gestion_permissions'),
    path('permissions/update/<int:comptable_id>/', update_permissions, name='update_permissions'),
    path('permissions/bulk-update/', bulk_update_permissions, name='bulk_update_permissions'),
    path('permissions/export/', export_permissions_csv, name='export_permissions_csv'),

    # AJAX endpoints
    path('ajax/toggle-permission/', ajax_toggle_permission, name='ajax_toggle_permission'),
    path('ajax/user-permissions/', ajax_user_permissions, name='ajax_user_permissions'),

    # Sécurité
    path('security/', security_dashboard, name='security_dashboard'),
    path('security/lockdown/', security_lockdown, name='security_lockdown'),
    path('security/unlock/', security_unlock, name='security_unlock'),
    path('security/clear-login-lock/', security_clear_login_lock, name='security_clear_login_lock'),
    path('security/admin-unlock/', admin_unlock, name='admin_unlock'),
]
