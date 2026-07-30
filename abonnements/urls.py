from django.urls import path
from django.views.generic import RedirectView

app_name = 'abonnements'

# NOTE : cette application est un doublon hérité, incomplet (plusieurs templates
# manquants) et remplacé par l'application `bus`, qui est complète et branchée
# dans le menu. Pour éviter toute page cassée, toutes ses routes redirigent
# désormais vers le module Bus / Cantine actif. Les modèles et migrations sont
# conservés (données/synchronisation) mais l'ancienne interface n'est plus servie.
urlpatterns = [
    path('', RedirectView.as_view(pattern_name='bus:index', permanent=False), name='tableau_bord'),

    # Bus -> app `bus`
    path('bus/', RedirectView.as_view(pattern_name='bus:index', permanent=False), name='liste_bus'),
    path('bus/nouveau/', RedirectView.as_view(pattern_name='bus:nouveau', permanent=False), name='creer_bus'),

    # Cantine -> app `bus` (views_cantine)
    path('cantine/', RedirectView.as_view(pattern_name='bus:liste_abonnements_cantine', permanent=False), name='liste_cantine'),
    path('cantine/nouveau/', RedirectView.as_view(pattern_name='bus:creer_abonnement_cantine', permanent=False), name='creer_cantine'),
    path('cantine/presences/', RedirectView.as_view(pattern_name='bus:tableau_bord_cantine', permanent=False), name='presences_cantine'),
    path('cantine/presences/enregistrer/', RedirectView.as_view(pattern_name='bus:tableau_bord_cantine', permanent=False), name='enregistrer_presence'),
]
