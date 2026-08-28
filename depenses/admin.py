from django.contrib import admin
from .models import (
    CategorieDepense, Fournisseur, Depense, PieceJustificative,
    BudgetAnnuel, HistoriqueDepense
)
from .models_logistique import (
    BienEtablissement, ContributionPapierRam
)
from .models_fournitures import ProduitFourniture, VenteFourniture
from .models_bibliotheque import (
    CategorieLivre, Livre, Emprunt, Reservation,
    HistoriqueLivre, ParametreBibliotheque
)
from .models_recouvrement import AbonnementInformatique


# ===== DÉPENSES =====
@admin.register(CategorieDepense)
class CategorieDepenseAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'actif']
    list_filter = ['actif']
    search_fields = ['nom', 'code']


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_fournisseur', 'telephone', 'email', 'actif']
    list_filter = ['type_fournisseur', 'actif']
    search_fields = ['nom', 'telephone', 'email']


@admin.register(Depense)
class DepenseAdmin(admin.ModelAdmin):
    list_display = ['numero_facture', 'libelle', 'fournisseur', 'montant_ttc', 'date_facture', 'statut']
    list_filter = ['statut', 'type_depense', 'categorie']
    search_fields = ['numero_facture', 'libelle', 'fournisseur__nom']
    date_hierarchy = 'date_facture'


# ===== LOGISTIQUE =====
@admin.register(BienEtablissement)
class BienEtablissementAdmin(admin.ModelAdmin):
    list_display = [
        'code_bien', 'nom', 'ecole', 'marque', 'quantite_achetee',
        'quantite_utilisee', 'quantite_gatee', 'quantite_disponible', 'actif'
    ]
    list_filter = ['ecole', 'type_bien', 'actif']
    search_fields = ['code_bien', 'nom', 'marque', 'localisation']
    readonly_fields = ['quantite_disponible', 'valeur_totale_achat']


@admin.register(ContributionPapierRam)
class ContributionPapierRamAdmin(admin.ModelAdmin):
    list_display = [
        'eleve', 'ecole', 'annee_scolaire', 'mode_contribution',
        'nombre_paquets', 'montant_paye', 'date_contribution'
    ]
    list_filter = ['ecole', 'annee_scolaire', 'mode_contribution']
    search_fields = ['eleve__matricule', 'eleve__nom', 'eleve__prenom']
    date_hierarchy = 'date_contribution'


# ===== RECOUVREMENT INFORMATIQUE =====
@admin.register(AbonnementInformatique)
class AbonnementInformatiqueAdmin(admin.ModelAdmin):
    """Gestion et suppression des abonnements informatique depuis Django admin."""

    list_display = [
        'eleve', 'ecole', 'date_debut', 'date_fin', 'montant', 'statut',
    ]
    list_filter = ['ecole', 'date_debut', 'date_fin']
    search_fields = [
        'eleve__matricule', 'eleve__nom', 'eleve__prenom',
    ]
    date_hierarchy = 'date_debut'
    list_select_related = ['eleve', 'eleve__classe', 'ecole']
    raw_id_fields = ['eleve']
    readonly_fields = ['date', 'date_creation', 'date_modification']


@admin.register(ProduitFourniture)
class ProduitFournitureAdmin(admin.ModelAdmin):
    list_display = [
        'code_produit', 'nom', 'ecole', 'quantite_stock',
        'quantite_vendue', 'quantite_restante',
        'prix_achat_unitaire', 'prix_vente_unitaire', 'actif',
    ]
    list_filter = ['ecole', 'actif']
    search_fields = ['code_produit', 'nom', 'description']
    readonly_fields = ['quantite_vendue', 'quantite_restante', 'chiffre_affaires', 'solde']


@admin.register(VenteFourniture)
class VenteFournitureAdmin(admin.ModelAdmin):
    list_display = [
        'reference', 'produit', 'date_vente', 'quantite',
        'prix_vente_unitaire', 'montant_total', 'solde',
    ]
    list_filter = ['produit__ecole', 'date_vente']
    search_fields = ['reference', 'produit__nom', 'acheteur']
    date_hierarchy = 'date_vente'


# ===== BIBLIOTHÈQUE =====
@admin.register(CategorieLivre)
class CategorieLivreAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'actif']
    list_filter = ['actif']
    search_fields = ['nom', 'code']


@admin.register(Livre)
class LivreAdmin(admin.ModelAdmin):
    list_display = ['code_livre', 'titre', 'auteur', 'categorie', 'statut', 'exemplaires_disponibles', 'etat']
    list_filter = ['categorie', 'statut', 'etat', 'langue']
    search_fields = ['code_livre', 'isbn', 'titre', 'auteur', 'editeur']
    readonly_fields = ['est_disponible', 'taux_disponibilite']


@admin.register(Emprunt)
class EmpruntAdmin(admin.ModelAdmin):
    list_display = ['numero_emprunt', 'livre', 'eleve', 'date_emprunt', 'date_retour_prevue', 'statut', 'jours_retard']
    list_filter = ['statut', 'date_emprunt']
    search_fields = ['numero_emprunt', 'livre__titre', 'eleve__nom', 'eleve__prenom']
    date_hierarchy = 'date_emprunt'
    readonly_fields = ['est_en_retard', 'jours_restants']


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ['numero_reservation', 'livre', 'eleve', 'date_reservation', 'statut']
    list_filter = ['statut', 'date_reservation']
    search_fields = ['numero_reservation', 'livre__titre', 'eleve__nom']
    date_hierarchy = 'date_reservation'


@admin.register(ParametreBibliotheque)
class ParametreBibliothequeAdmin(admin.ModelAdmin):
    list_display = ['duree_emprunt_defaut', 'nombre_emprunts_max', 'penalite_retard_journalier']
    
    def has_add_permission(self, request):
        # Permettre seulement un seul enregistrement
        return not ParametreBibliotheque.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        return False
