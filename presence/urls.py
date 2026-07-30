from django.urls import path
from . import views

app_name = 'presence'

urlpatterns = [
    path('', views.pointage, name='pointage'),
    path('rapport/', views.rapport_presence, name='rapport'),
    path('rapport/pdf/', views.rapport_presence_pdf, name='rapport_pdf'),
    path('rapport/excel/', views.rapport_presence_excel, name='rapport_excel'),
    path('alertes/', views.alertes_absences, name='alertes'),
]
