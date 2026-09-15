from django.contrib import admin
from .models import SystemLog, MaintenanceMode, VersionApplication


@admin.register(SystemLog)
class SystemLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'action', 'description', 'user', 'ip_address']
    list_filter = ['action', 'timestamp']
    search_fields = ['description', 'user__username', 'ip_address']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def has_add_permission(self, request):
        # Les logs ne peuvent pas être ajoutés manuellement
        return False
    
    def has_change_permission(self, request, obj=None):
        # Les logs ne peuvent pas être modifiés
        return False


@admin.register(MaintenanceMode)
class MaintenanceModeAdmin(admin.ModelAdmin):
    list_display = ['is_active', 'activated_by', 'activated_at']
    fields = ['is_active', 'message', 'allowed_users']
    filter_horizontal = ['allowed_users']
    
    def save_model(self, request, obj, form, change):
        if obj.is_active and not obj.activated_by:
            obj.activated_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(VersionApplication)
class VersionApplicationAdmin(admin.ModelAdmin):
    """Diffusion des mises a jour de l'application Windows."""

    list_display = ['version', 'publiee', 'obligatoire', 'date_publication', 'date_creation']
    list_filter = ['publiee', 'obligatoire']
    search_fields = ['version', 'notes']
    readonly_fields = ['date_creation', 'date_publication']
    fieldsets = (
        ('Version', {
            'fields': ('version', 'notes'),
        }),
        ('Fichier a installer', {
            'fields': ('url_telechargement', 'sha256', 'taille_octets'),
            'description': (
                "L'empreinte SHA-256 est verifiee sur le poste avant que "
                "l'installateur ne soit lance. Sous Windows, on l'obtient par "
                "<code>certutil -hashfile installateur.exe SHA256</code>."
            ),
        }),
        ('Diffusion', {
            'fields': ('publiee', 'obligatoire', 'date_publication', 'date_creation'),
            'description': (
                "Tant que <em>publiee</em> reste decoche, aucun poste ne voit "
                "cette version."
            ),
        }),
    )
