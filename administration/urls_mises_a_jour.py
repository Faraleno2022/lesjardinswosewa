from django.urls import path

from . import views_mises_a_jour

app_name = 'mises_a_jour'

urlpatterns = [
    path('latest/', views_mises_a_jour.derniere_version, name='derniere_version'),
    path('prete/', views_mises_a_jour.mise_a_jour_prete, name='mise_a_jour_prete'),
]
