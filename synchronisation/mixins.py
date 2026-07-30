import uuid

from django.db import models


class SyncTrackedModel(models.Model):
    sync_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    sync_created_at = models.DateTimeField(auto_now_add=True)
    sync_updated_at = models.DateTimeField(auto_now=True)
    sync_deleted_at = models.DateTimeField(null=True, blank=True)
    sync_version = models.PositiveIntegerField(default=1)
    is_synced = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True
