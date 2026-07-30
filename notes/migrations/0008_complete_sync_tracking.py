import uuid

import django.utils.timezone
from django.db import migrations, models


MODEL_NAMES = ['themebulletin', 'analysetravailmaternelle', 'recommandationmaternelle', 'piecejointeactivite']


def populate_sync_uuid(apps, schema_editor):
    for model_name in MODEL_NAMES:
        model = apps.get_model('notes', model_name)
        for obj in model.objects.filter(sync_uuid__isnull=True).only('pk', 'sync_uuid'):
            obj.sync_uuid = uuid.uuid4()
            obj.save(update_fields=['sync_uuid'])


def sync_fields(model_name):
    return [
        migrations.AddField(model_name=model_name, name='sync_uuid', field=models.UUIDField(db_index=True, editable=False, null=True)),
        migrations.AddField(model_name=model_name, name='sync_created_at', field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now), preserve_default=False),
        migrations.AddField(model_name=model_name, name='sync_updated_at', field=models.DateTimeField(auto_now=True)),
        migrations.AddField(model_name=model_name, name='sync_deleted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name=model_name, name='sync_version', field=models.PositiveIntegerField(default=1)),
        migrations.AddField(model_name=model_name, name='is_synced', field=models.BooleanField(db_index=True, default=False)),
    ]


def sync_uuid_constraints(model_name):
    return [
        migrations.AlterField(model_name=model_name, name='sync_uuid', field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
    ]


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0007_add_sync_tracking'),
    ]

    operations = sum((sync_fields(model_name) for model_name in MODEL_NAMES), [])
    operations += [migrations.RunPython(populate_sync_uuid, migrations.RunPython.noop)]
    operations += sum((sync_uuid_constraints(model_name) for model_name in MODEL_NAMES), [])
