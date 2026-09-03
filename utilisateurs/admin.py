from django.contrib import admin
from .models import Profil


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
