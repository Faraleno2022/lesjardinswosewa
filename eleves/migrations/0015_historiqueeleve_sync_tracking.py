import uuid

import django.utils.timezone
from django.db import migrations, models


def populate_sync_uuid(apps, schema_editor):
    model = apps.get_model('eleves', 'historiqueeleve')
    for obj in model.objects.filter(sync_uuid__isnull=True).only('pk', 'sync_uuid'):
        obj.sync_uuid = uuid.uuid4()
        obj.save(update_fields=['sync_uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('eleves', '0014_add_sync_tracking'),
    ]

    operations = [
        migrations.AddField(
            model_name='historiqueeleve',
            name='sync_uuid',
            field=models.UUIDField(db_index=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='historiqueeleve',
            name='sync_created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='historiqueeleve',
            name='sync_updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name='historiqueeleve',
            name='sync_deleted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='historiqueeleve',
            name='sync_version',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='historiqueeleve',
            name='is_synced',
            field=models.BooleanField(db_index=True, default=False),
        ),
        migrations.RunPython(populate_sync_uuid, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='historiqueeleve',
            name='sync_uuid',
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
