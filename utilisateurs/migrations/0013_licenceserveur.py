from django.db import migrations, models
import utilisateurs.models


class Migration(migrations.Migration):

    dependencies = [
        ('utilisateurs', '0012_profil_peut_importer_eleves_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='LicenceServeur',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('license_key', models.CharField(default=utilisateurs.models.generate_license_key_value, max_length=29, unique=True, verbose_name='Clé de licence')),
                ('machine_id', models.CharField(max_length=64, verbose_name='ID machine')),
                ('school', models.CharField(max_length=120, verbose_name='École')),
                ('edition', models.CharField(default='Standard', max_length=30, verbose_name='Édition')),
                ('deploiement', models.CharField(default='local', max_length=30, verbose_name='Déploiement')),
                ('status', models.CharField(choices=[('active', 'Active'), ('suspended', 'Suspendue'), ('expired', 'Expirée'), ('revoked', 'Révoquée')], default='active', max_length=20, verbose_name='Statut')),
                ('expires_at', models.DateField(verbose_name="Date d'expiration")),
                ('hostname', models.CharField(blank=True, max_length=120, verbose_name='Nom de machine')),
                ('activated_at', models.DateTimeField(blank=True, null=True, verbose_name='Activée le')),
                ('last_check_at', models.DateTimeField(blank=True, null=True, verbose_name='Dernière vérification')),
                ('notes', models.TextField(blank=True, verbose_name='Notes')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Créée le')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Modifiée le')),
            ],
            options={
                'verbose_name': 'Licence serveur',
                'verbose_name_plural': 'Licences serveur',
                'ordering': ['-created_at'],
            },
        ),
    ]
