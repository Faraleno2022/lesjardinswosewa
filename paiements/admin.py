from django.contrib import admin
from .models import TypePaiement, ModePaiement, Paiement, RemiseReduction, EcheancierPaiement, TwilioInboundMessage, ConfigurationPaiement


@admin.register(TypePaiement)
class TypePaiementAdmin(admin.ModelAdmin):
    list_display = ("nom", "actif")
    search_fields = ("nom",)
    list_filter = ("actif",)


@admin.register(ModePaiement)
class ModePaiementAdmin(admin.ModelAdmin):
    list_display = ("nom", "frais_supplementaires", "actif")
    search_fields = ("nom",)
    list_filter = ("actif",)


@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ("numero_recu", "eleve", "type_paiement", "mode_paiement", "montant", "date_paiement", "statut")
    search_fields = ("numero_recu", "eleve__nom", "eleve__prenom", "eleve__matricule")
    list_filter = ("statut", "type_paiement", "mode_paiement")
    date_hierarchy = "date_paiement"


@admin.register(RemiseReduction)
class RemiseReductionAdmin(admin.ModelAdmin):
    list_display = ("nom", "type_remise", "valeur", "motif", "actif")
    search_fields = ("nom",)
    list_filter = ("type_remise", "motif", "actif")


@admin.register(EcheancierPaiement)
class EcheancierPaiementAdmin(admin.ModelAdmin):
    list_display = ("eleve", "annee_scolaire", "statut", "total_du", "total_paye")
    search_fields = ("eleve__nom", "eleve__prenom", "eleve__matricule")


@admin.register(TwilioInboundMessage)
class TwilioInboundMessageAdmin(admin.ModelAdmin):
    list_display = ("received_at", "channel", "from_number", "to_number", "message_sid", "delivery_status")
    list_filter = ("channel", "delivery_status")
    search_fields = ("from_number", "to_number", "message_sid", "body")
    date_hierarchy = "received_at"


@admin.register(ConfigurationPaiement)
class ConfigurationPaiementAdmin(admin.ModelAdmin):
    list_display = ("classe", "montant_inscription", "montant_scolarite", "nombre_tranches", "montant_total")
    search_fields = ("classe__nom", "classe__ecole__nom")
    list_filter = ("nombre_tranches", "classe__niveau")
    readonly_fields = ("montant_total", "montant_par_tranche", "repartition_tranches_affichage",
                       "date_creation", "date_modification")

    @admin.display(description="Répartition exacte des tranches (somme = scolarité)")
    def repartition_tranches_affichage(self, obj):
        if not obj or not obj.pk:
            return "-"
        tranches = obj.repartition_tranches()
        if not tranches:
            return "-"
        details = " + ".join(f"{t:,.0f}" for t in tranches)
        return f"{details} = {sum(tranches):,.0f} GNF"
