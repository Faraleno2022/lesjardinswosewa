from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Pages principales
    path('', views.chatbot_home, name='home'),
    path('chat/', views.chat_interface, name='chat'),
    path('chat/<int:matiere_id>/', views.chat_interface, name='chat_matiere'),
    path('nouvelle-conversation/', views.nouvelle_conversation, name='nouvelle_conversation'),
    
    # Documents
    path('documents/', views.liste_documents, name='documents'),
    path('documents/<int:document_id>/', views.detail_document, name='detail_document'),
    
    # Administration (staff uniquement)
    path('admin/documents/', views.gestion_documents, name='gestion_documents'),
    path('admin/documents/ajouter/', views.ajouter_document, name='ajouter_document'),
    path('admin/documents/<int:document_id>/supprimer/', views.supprimer_document, name='supprimer_document'),
    path('admin/matieres/', views.gestion_matieres, name='gestion_matieres'),
    
    # API
    path('api/envoyer/', views.envoyer_message, name='api_envoyer'),
    path('api/matieres/', views.api_matieres, name='api_matieres'),
    path('api/suggestions/', views.api_suggestions, name='api_suggestions'),
]
