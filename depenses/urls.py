from django.urls import path
from . import views
from . import views_logistique
from . import views_bibliotheque
from . import views_fournitures
from . import views_recouvrement
from . import views_personnel

app_name = 'depenses'

urlpatterns = [
    # Tableau de bord principal
    path('', views.tableau_bord, name='tableau_bord'),
    
    # Gestion des dépenses
    path('liste/', views.liste_depenses, name='liste_depenses'),
    path('ajouter/', views.ajouter_depense, name='ajouter_depense'),
    path('<int:depense_id>/', views.detail_depense, name='detail_depense'),
    path('<int:depense_id>/modifier/', views.modifier_depense, name='modifier_depense'),
    path('<int:depense_id>/supprimer/', views.supprimer_depense, name='supprimer_depense'),
    path('<int:depense_id>/valider/', views.valider_depense, name='valider_depense'),
    path('<int:depense_id>/marquer-payee/', views.marquer_payee, name='marquer_payee'),
    
    # Gestion des catégories
    path('categories/', views.gestion_categories, name='gestion_categories'),
    path('categories/<int:categorie_id>/modifier/', views.modifier_categorie, name='modifier_categorie'),
    path('categories/<int:categorie_id>/supprimer/', views.supprimer_categorie, name='supprimer_categorie'),

    # ===== FOURNITURES SCOLAIRES ET VENTES =====
    path('fournitures/', views_fournitures.tableau_bord_fournitures, name='tableau_bord_fournitures'),
    path('fournitures/produits/nouveau/', views_fournitures.creer_produit_fourniture, name='creer_produit_fourniture'),
    path('fournitures/produits/<int:produit_id>/modifier/', views_fournitures.modifier_produit_fourniture, name='modifier_produit_fourniture'),
    path('fournitures/produits/<int:produit_id>/vendre/', views_fournitures.enregistrer_vente_fourniture, name='enregistrer_vente_fourniture'),
    path('fournitures/produits/<int:produit_id>/supprimer/', views_fournitures.supprimer_produit_fourniture, name='supprimer_produit_fourniture'),
    path('fournitures/ventes/<int:vente_id>/annuler/', views_fournitures.annuler_vente_fourniture, name='annuler_vente_fourniture'),
    
    # ===== LOGISTIQUE =====
    path('logistique/', views_logistique.dashboard_logistique, name='dashboard_logistique'),
    path('logistique/biens/', views_logistique.liste_biens, name='liste_biens'),
    path('logistique/biens/nouveau/', views_logistique.creer_bien, name='creer_bien'),
    path('logistique/biens/<int:bien_id>/modifier/', views_logistique.modifier_bien, name='modifier_bien'),
    path('logistique/biens/<int:bien_id>/archiver/', views_logistique.archiver_bien, name='archiver_bien'),
    path('logistique/papier-ram/', views_logistique.gestion_papier_ram, name='gestion_papier_ram'),
    path('logistique/papier-ram/nouveau/', views_logistique.ajouter_papier_ram, name='ajouter_papier_ram'),
    path('logistique/papier-ram/<int:contribution_id>/modifier/', views_logistique.modifier_papier_ram, name='modifier_papier_ram'),
    path('logistique/papier-ram/<int:contribution_id>/supprimer/', views_logistique.supprimer_papier_ram, name='supprimer_papier_ram'),
    
    # ===== BIBLIOTHÈQUE =====
    path('bibliotheque/', views_bibliotheque.dashboard_bibliotheque, name='dashboard_bibliotheque'),
    path('bibliotheque/catalogue/', views_bibliotheque.catalogue_livres, name='catalogue_livres'),
    path('bibliotheque/catalogue/nouveau/', views_bibliotheque.creer_livre, name='creer_livre'),
    path('bibliotheque/catalogue/<int:livre_id>/modifier/', views_bibliotheque.modifier_livre, name='modifier_livre'),
    path('bibliotheque/catalogue/<int:livre_id>/supprimer/', views_bibliotheque.supprimer_livre, name='supprimer_livre'),
    path('bibliotheque/categories/', views_bibliotheque.gestion_categories_livres, name='gestion_categories_livres'),
    path('bibliotheque/categories/<int:categorie_id>/modifier/', views_bibliotheque.modifier_categorie_livre, name='modifier_categorie_livre'),
    path('bibliotheque/categories/<int:categorie_id>/supprimer/', views_bibliotheque.supprimer_categorie_livre, name='supprimer_categorie_livre'),
    path('bibliotheque/emprunts/', views_bibliotheque.liste_emprunts, name='liste_emprunts'),
    path('bibliotheque/emprunts/nouveau/', views_bibliotheque.creer_emprunt, name='creer_emprunt'),
    path('bibliotheque/emprunts/<int:emprunt_id>/retour/', views_bibliotheque.retourner_livre, name='retourner_livre'),
    path('bibliotheque/reservations/', views_bibliotheque.liste_reservations, name='liste_reservations'),
    path('bibliotheque/reservations/nouvelle/', views_bibliotheque.creer_reservation, name='creer_reservation'),
    path('bibliotheque/reservations/<int:reservation_id>/annuler/', views_bibliotheque.annuler_reservation, name='annuler_reservation'),
    path('bibliotheque/statistiques/', views_bibliotheque.statistiques_bibliotheque, name='statistiques_bibliotheque'),

    # ---- Recouvrement : portail, modules simples et informatique ----
    path('recouvrement/', views_recouvrement.hub_recouvrement, name='recouvrement_hub'),
    path('recouvrement/informatique/', views_recouvrement.informatique_liste, name='informatique_liste'),
    path('recouvrement/informatique/nouveau/', views_recouvrement.informatique_nouveau, name='informatique_nouveau'),
    path('recouvrement/informatique/nouveau/<int:eleve_id>/', views_recouvrement.informatique_nouveau, name='informatique_nouveau_eleve'),
    path('recouvrement/informatique/tableau-bord/', views_recouvrement.informatique_tableau_bord, name='informatique_tableau_bord'),
    path('recouvrement/informatique/<int:pk>/carte/', views_recouvrement.informatique_carte, name='informatique_carte'),
    path('recouvrement/informatique/export/excel/', views_recouvrement.informatique_export_excel, name='informatique_export_excel'),
    path('recouvrement/informatique/export/pdf/', views_recouvrement.informatique_export_pdf, name='informatique_export_pdf'),
    path('recouvrement/personnel/', views_personnel.personnel_dashboard, name='personnel_dashboard'),
    path('recouvrement/personnel/export/excel/', views_personnel.personnel_export_excel, name='personnel_export_excel'),
    path('recouvrement/personnel/<int:pk>/modifier/', views_personnel.personnel_modifier, name='personnel_modifier'),
    path('recouvrement/personnel/<int:pk>/supprimer/', views_personnel.personnel_supprimer, name='personnel_supprimer'),
    path('recouvrement/<str:cle>/', views_recouvrement.liste_operations, name='recouvrement_liste'),
    path('recouvrement/<str:cle>/tableau-bord/', views_recouvrement.tableau_bord_module, name='recouvrement_tableau_bord'),
    path('recouvrement/<str:cle>/export/excel/', views_recouvrement.export_excel_module, name='recouvrement_export_excel'),
    path('recouvrement/<str:cle>/export/pdf/', views_recouvrement.export_pdf_module, name='recouvrement_export_pdf'),
    path('recouvrement/<str:cle>/<int:pk>/modifier/', views_recouvrement.modifier_operation, name='recouvrement_modifier'),
    path('recouvrement/<str:cle>/<int:pk>/supprimer/', views_recouvrement.supprimer_operation, name='recouvrement_supprimer'),
]
