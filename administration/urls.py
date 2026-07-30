from django.urls import path
from . import views

app_name = 'administration'

urlpatterns = [
    # Tableau de bord principal
    path('', views.dashboard, name='dashboard'),
    
    # Gestion des utilisateurs
    path('users/', views.users_management, name='users_management'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    
    # Statistiques et monitoring
    path('stats/', views.system_stats, name='system_stats'),
    path('logs/', views.system_logs, name='system_logs'),
    
    # Actions système
    path('maintenance/toggle/', views.toggle_maintenance, name='toggle_maintenance'),
    path('logs/clear/', views.clear_old_logs, name='clear_old_logs'),
    path('ecoles/<int:ecole_id>/valider/', views.valider_ecole, name='valider_ecole'),
    path('ecoles/<int:ecole_id>/rejeter/', views.rejeter_ecole, name='rejeter_ecole'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active, name='user_toggle_active'),
    path('users/<int:user_id>/toggle-staff/', views.user_toggle_staff, name='user_toggle_staff'),
    path('users/<int:user_id>/reset-password/', views.user_reset_password, name='user_reset_password'),
    path('users/<int:user_id>/activate-and-validate/', views.user_activate_and_validate, name='user_activate_and_validate'),
    
    # Corbeille et restauration
    path('corbeille/', views.corbeille_list, name='corbeille_list'),
    path('corbeille/restaurer/<int:log_id>/', views.restaurer_element, name='restaurer_element'),
]
