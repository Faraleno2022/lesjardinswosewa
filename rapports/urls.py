from django.urls import path
from . import views

app_name = 'rapports'

urlpatterns = [
    path('', views.tableau_bord, name='tableau_bord'),
    path('journalier/', views.generer_rapport_journalier, name='rapport_journalier'),
    path('journalier/export/excel/', views.export_rapport_journalier_excel, name='export_rapport_journalier_excel'),
    path('hebdomadaire/', views.generer_rapport_hebdomadaire, name='rapport_hebdomadaire'),
    path('hebdomadaire/export/excel/', views.export_rapport_hebdomadaire_excel, name='export_rapport_hebdomadaire_excel'),
    path('mensuel/', views.generer_rapport_mensuel, name='rapport_mensuel'),
    path('mensuel/export/excel/', views.export_rapport_mensuel_excel, name='export_rapport_mensuel_excel'),
    path('annuel/', views.generer_rapport_annuel, name='rapport_annuel'),
    path('annuel/export/excel/', views.export_rapport_annuel_excel, name='export_rapport_annuel_excel'),
    path('liste/', views.liste_rapports, name='liste_rapports'),
    path('remises/', views.rapport_remises_detaille, name='rapport_remises'),
    path('transport/', views.rapport_transport_scolaire, name='rapport_transport'),
]
