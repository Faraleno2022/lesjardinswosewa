from django.contrib import admin
from django.utils.html import format_html
from .models import LicenceServeur, Profil


@admin.register(LicenceServeur)
class LicenceServeurAdmin(admin.ModelAdmin):
    list_display = (
        'school', 'license_key', 'machine_id_short', 'edition',
        'status', 'expires_at', 'days_left_display', 'activated_at',
    )
    list_filter = ('status', 'edition', 'deploiement', 'expires_at')
    search_fields = ('license_key', 'machine_id', 'school', 'hostname')
    readonly_fields = ('license_key', 'activated_at', 'last_check_at', 'created_at', 'updated_at')
    fieldsets = (
        ('Licence', {
            'fields': ('license_key', 'status', 'school', 'edition', 'deploiement', 'expires_at')
        }),
        ('Machine cliente', {
            'fields': ('machine_id', 'hostname')
        }),
        ('Suivi', {
            'fields': ('activated_at', 'last_check_at', 'notes', 'created_at', 'updated_at')
        }),
    )

    @admin.display(description="Machine")
    def machine_id_short(self, obj):
        return obj.machine_id[:16] + "..." if obj.machine_id else ""

    @admin.display(description="Jours restants")
    def days_left_display(self, obj):
        days = obj.days_left
        color = "#16a34a" if days > 30 else "#dc2626" if days <= 7 else "#d97706"
        return format_html('<strong style="color:{}">{} j</strong>', color, days)


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'telephone', 'ecole', 'actif')
    list_filter = ('role', 'ecole', 'actif')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'telephone')
    autocomplete_fields = ('user', 'ecole')

    def get_readonly_fields(self, request, obj=None):
        """Empêche la modification du téléphone pour les non-superusers."""
        base = super().get_readonly_fields(request, obj)
        if request.user and not request.user.is_superuser:
            return tuple(base) + ('telephone',)
        return base
