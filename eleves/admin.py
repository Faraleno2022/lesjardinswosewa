import json
import secrets

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html
from .models import Ecole, Classe, Eleve, EleveCorbeille, GrilleTarifaire


@admin.register(Ecole)
class EcoleAdmin(admin.ModelAdmin):
    list_display = (
        "nom", "etat", "code_prefixe", "telephone", "email", "directeur",
        "censeur", "created_by", "logo_mini", "configuration_offline",
    )
    list_filter = ("etat",)
    search_fields = ("nom", "directeur", "censeur", "telephone", "email")
    readonly_fields = ("logo_preview", "image_preview", "configuration_offline")
    fieldsets = (
        ("Identité", {
            "fields": ("nom", "directeur", "censeur", "etat", "created_by")
        }),
        ("Paramètres matricules", {
            "fields": ("code_prefixe",),
            "description": "Préfixe d'école pour les matricules (ex: AL-FUR/). Laissez vide pour ne pas utiliser de préfixe explicite."
        }),
        ("Coordonnées", {
            "fields": ("adresse", "telephone", "telephone2", "telephone3", "email")
        }),
        ("Logo & Image", {
            "fields": ("logo", "logo_preview", "image", "image_preview"),
            "description": "Logo pour filigrane et en-tetes. Photo de l'ecole pour le livret scolaire."
        }),
        ("Version hors ligne", {
            "fields": ("configuration_offline",),
            "description": "Créez une connexion sécurisée propre à cette école pour chaque poste hors ligne."
        }),
    )
    actions = ("valider_ecoles", "rejeter_ecoles")

    def get_urls(self):
        custom_urls = [
            path(
                '<path:object_id>/version-hors-ligne/',
                self.admin_site.admin_view(self.version_hors_ligne_view),
                name='eleves_ecole_version_hors_ligne',
            ),
        ]
        return custom_urls + super().get_urls()

    @admin.display(description="Version hors ligne")
    def configuration_offline(self, obj):
        if not obj or not obj.pk:
            return "Enregistrez d'abord l'école."
        url = reverse('admin:eleves_ecole_version_hors_ligne', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Configurer la version hors ligne</a>',
            url,
        )

    def _verifier_acces_ecole(self, request, ecole):
        if not self.has_change_permission(request, ecole):
            raise PermissionDenied
        if request.user.is_superuser:
            return

        from utilisateurs.utils import user_is_admin, user_school

        if not user_is_admin(request.user) or user_school(request.user) != ecole:
            raise PermissionDenied

    def _url_serveur_sync(self, request):
        public_url = getattr(settings, 'MYSCHOOL_SYNC_PUBLIC_URL', '').strip()
        return (public_url or request.build_absolute_uri('/')).rstrip('/')

    def version_hors_ligne_view(self, request, object_id):
        """Génère ou révoque les accès offline d'une école donnée."""
        from synchronisation.models import SyncDevice

        ecole = get_object_or_404(self.get_queryset(request), pk=object_id)
        self._verifier_acces_ecole(request, ecole)
        page_url = reverse('admin:eleves_ecole_version_hors_ligne', args=[ecole.pk])

        if request.method == 'POST':
            action = request.POST.get('action')

            if action == 'revoquer':
                device = SyncDevice.objects.filter(
                    pk=request.POST.get('device_id'), ecole=ecole,
                ).first()
                if not device:
                    messages.error(request, "Poste introuvable pour cette école.")
                elif not device.actif:
                    messages.info(request, "Ce poste est déjà révoqué.")
                else:
                    device.actif = False
                    device.save(update_fields=['actif', 'date_modification'])
                    messages.success(request, f"L'accès du poste « {device.nom} » a été révoqué.")
                return redirect(page_url)

            if action == 'creer':
                nom = (request.POST.get('nom') or 'Poste local').strip()[:120]
                try:
                    intervalle = int(request.POST.get('intervalle') or 60)
                except (TypeError, ValueError):
                    intervalle = 0

                if not nom:
                    messages.error(request, "Indiquez le nom du poste.")
                    return redirect(page_url)
                if intervalle < 10 or intervalle > 3600:
                    messages.error(request, "L'intervalle doit être compris entre 10 et 3 600 secondes.")
                    return redirect(page_url)

                token = secrets.token_urlsafe(32)
                with transaction.atomic():
                    device = SyncDevice(ecole=ecole, nom=nom)
                    device.definir_token(token)
                    device.save()

                configuration = {
                    'MYSCHOOL_SYNC_SERVER_URL': self._url_serveur_sync(request),
                    'MYSCHOOL_SYNC_ECOLE_ID': ecole.pk,
                    'MYSCHOOL_SYNC_DEVICE_ID': str(device.device_id),
                    'MYSCHOOL_SYNC_TOKEN': token,
                    'MYSCHOOL_SYNC_INTERVAL': intervalle,
                }
                response = HttpResponse(
                    json.dumps(configuration, ensure_ascii=False, indent=2),
                    content_type='application/json; charset=utf-8',
                )
                response['Content-Disposition'] = 'attachment; filename="sync_config.json"'
                response['Cache-Control'] = 'no-store, private, max-age=0'
                response['Pragma'] = 'no-cache'
                response['X-Content-Type-Options'] = 'nosniff'
                return response

            messages.error(request, "Action de configuration inconnue.")
            return redirect(page_url)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Version hors ligne — {ecole.nom}',
            'opts': self.model._meta,
            'original': ecole,
            'ecole': ecole,
            'devices': SyncDevice.objects.filter(ecole=ecole).order_by('-date_creation'),
            'change_url': reverse('admin:eleves_ecole_change', args=[ecole.pk]),
            'server_url': self._url_serveur_sync(request),
        }
        return TemplateResponse(
            request,
            'admin/eleves/ecole/version_hors_ligne.html',
            context,
        )

    def valider_ecoles(self, request, queryset):
        updated = queryset.update(etat="VALIDE")
        self.message_user(request, f"{updated} école(s) validée(s).")
    valider_ecoles.short_description = "Valider les écoles sélectionnées"

    def rejeter_ecoles(self, request, queryset):
        updated = queryset.update(etat="REJETE")
        self.message_user(request, f"{updated} école(s) rejetée(s).")
    rejeter_ecoles.short_description = "Rejeter les écoles sélectionnées"

    def logo_preview(self, obj):
        if getattr(obj, 'logo', None) and getattr(obj.logo, 'url', None):
            return format_html('<img src="{}" style="max-height:80px; border:1px solid #ddd; padding:2px;" />', obj.logo.url)
        return "—"
    logo_preview.short_description = "Aperçu du logo"

    def logo_mini(self, obj):
        if getattr(obj, 'logo', None) and getattr(obj.logo, 'url', None):
            return format_html('<img src="{}" style="height:24px; width:auto;" />', obj.logo.url)
        return ""
    logo_mini.short_description = "Logo"

    def image_preview(self, obj):
        if getattr(obj, 'image', None) and getattr(obj.image, 'url', None):
            return format_html('<img src="{}" style="max-height:120px; border:1px solid #ddd; padding:2px;" />', obj.image.url)
        return "—"
    image_preview.short_description = "Apercu de l'image"


@admin.register(Classe)
class ClasseAdmin(admin.ModelAdmin):
    list_display = ("nom", "niveau", "annee_scolaire", "ecole")
    list_filter = ("ecole", "niveau", "annee_scolaire")
    search_fields = ("nom", "ecole__nom")


@admin.register(GrilleTarifaire)
class GrilleTarifaireAdmin(admin.ModelAdmin):
    list_display = (
        "ecole", "niveau", "annee_scolaire",
        "frais_inscription", "tranche_1", "tranche_2", "tranche_3",
    )
    list_filter = ("ecole", "niveau", "annee_scolaire")
    search_fields = ("ecole__nom",)
    fieldsets = (
        ("Ciblage", {
            "fields": ("ecole", "niveau", "annee_scolaire"),
        }),
        ("Montants", {
            "fields": (
                "frais_inscription", "frais_reinscription",
                "tranche_1", "tranche_2", "tranche_3",
            ),
        }),
        ("Périodes (texte)", {
            "classes": ("collapse",),
            "fields": ("periode_1", "periode_2", "periode_3"),
        }),
        ("Échéances par défaut (dates)", {
            "fields": (
                "date_echeance_inscription_defaut",
                "date_echeance_tranche_1_defaut",
                "date_echeance_tranche_2_defaut",
                "date_echeance_tranche_3_defaut",
            ),
            "description": "Si ces dates sont renseignées, elles seront utilisées pour initialiser les échéanciers des élèves de cette école/niveau/année."
        }),
    )


@admin.register(Eleve)
class EleveAdmin(admin.ModelAdmin):
    list_display = (
        'matricule', 'nom', 'prenom', 'classe', 'statut',
        'date_inscription',
    )
    list_filter = ('statut', 'classe__ecole', 'classe')
    search_fields = ('matricule', 'nom', 'prenom')
    list_select_related = ('classe', 'classe__ecole')
    actions = ('placer_dans_corbeille',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(est_dans_corbeille=False)

    @admin.action(description="Placer les élèves sélectionnés dans la corbeille")
    def placer_dans_corbeille(self, request, queryset):
        count = 0
        for eleve in queryset:
            count += int(eleve.placer_dans_corbeille(request.user))
        self.message_user(request, f"{count} élève(s) placé(s) dans la corbeille.")

    def delete_model(self, request, obj):
        obj.placer_dans_corbeille(request.user)

    def delete_queryset(self, request, queryset):
        for eleve in queryset:
            eleve.placer_dans_corbeille(request.user)


@admin.register(EleveCorbeille)
class EleveCorbeilleAdmin(admin.ModelAdmin):
    list_display = (
        'matricule', 'nom', 'prenom', 'classe', 'supprime_le', 'supprime_par',
    )
    list_filter = ('classe__ecole', 'classe', 'supprime_le')
    search_fields = ('matricule', 'nom', 'prenom')
    readonly_fields = (
        'matricule', 'nom', 'prenom', 'classe', 'statut',
        'supprime_le', 'supprime_par', 'statut_avant_suppression',
    )
    actions = ('restaurer_eleves',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(est_dans_corbeille=True)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Restaurer les élèves sélectionnés")
    def restaurer_eleves(self, request, queryset):
        count = 0
        for eleve in queryset:
            count += int(eleve.restaurer_depuis_corbeille())
        self.message_user(request, f"{count} élève(s) restauré(s).")
