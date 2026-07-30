from django.contrib import admin

from .models import SyncChange, SyncDevice


@admin.register(SyncDevice)
class SyncDeviceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'ecole', 'device_id', 'actif', 'derniere_connexion', 'date_creation')
    list_filter = ('actif', 'ecole')
    search_fields = ('nom', 'device_id', 'ecole__nom')
    readonly_fields = ('device_id', 'token_hash', 'derniere_connexion', 'date_creation', 'date_modification')


@admin.register(SyncChange)
class SyncChangeAdmin(admin.ModelAdmin):
    list_display = (
        'model_label', 'operation', 'statut', 'tentatives',
        'ecole', 'device', 'date_creation',
    )
    list_filter = ('operation', 'statut', 'ecole', 'model_label')
    search_fields = ('model_label', 'object_uuid', 'device__nom', 'ecole__nom')
    readonly_fields = ('date_creation', 'date_application')
