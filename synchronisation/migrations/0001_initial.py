# Generated for MySchoolGN offline/online sync foundation.

import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('eleves', '0013_add_image_ecole'),
    ]

    operations = [
        migrations.CreateModel(
            name='SyncDevice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nom', models.CharField(max_length=120)),
                ('device_id', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('token_hash', models.CharField(max_length=255)),
                ('actif', models.BooleanField(db_index=True, default=True)),
                ('derniere_connexion', models.DateTimeField(blank=True, null=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('ecole', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_devices', to='eleves.ecole')),
            ],
            options={
                'verbose_name': 'Appareil de synchronisation',
                'verbose_name_plural': 'Appareils de synchronisation',
            },
        ),
        migrations.CreateModel(
            name='SyncChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('model_label', models.CharField(max_length=120)),
                ('object_uuid', models.UUIDField(blank=True, db_index=True, null=True)),
                ('operation', models.CharField(choices=[('CREATE', 'Creation'), ('UPDATE', 'Modification'), ('DELETE', 'Suppression')], max_length=10)),
                ('payload', models.JSONField(blank=True, default=dict)),
                ('statut', models.CharField(choices=[('PENDING', 'En attente'), ('APPLIED', 'Applique'), ('FAILED', 'Echec')], db_index=True, default='PENDING', max_length=12)),
                ('erreur', models.TextField(blank=True)),
                ('date_creation', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('date_application', models.DateTimeField(blank=True, null=True)),
                ('device', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='changes', to='synchronisation.syncdevice')),
                ('ecole', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sync_changes', to='eleves.ecole')),
            ],
            options={
                'verbose_name': 'Changement synchronise',
                'verbose_name_plural': 'Changements synchronises',
            },
        ),
        migrations.AddIndex(
            model_name='syncdevice',
            index=models.Index(fields=['ecole', 'actif'], name='synchronisa_ecole_i_90f446_idx'),
        ),
        migrations.AddIndex(
            model_name='syncdevice',
            index=models.Index(fields=['derniere_connexion'], name='synchronisa_dernier_2d466f_idx'),
        ),
        migrations.AddIndex(
            model_name='syncchange',
            index=models.Index(fields=['ecole', 'statut', 'date_creation'], name='synchronisa_ecole_i_4c0290_idx'),
        ),
        migrations.AddIndex(
            model_name='syncchange',
            index=models.Index(fields=['model_label', 'object_uuid'], name='synchronisa_model_l_9e30cd_idx'),
        ),
    ]
