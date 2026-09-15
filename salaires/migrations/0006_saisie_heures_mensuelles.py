import uuid
from decimal import Decimal

import django.core.validators
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('salaires', '0005_etatsalaire_taux_horaire_applique_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='etatsalaire',
            name='source_heures',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', 'Non applicable'),
                    ('POINTAGE', 'Pointages arrivée / départ'),
                    ('SAISIE_MENSUELLE', 'Saisie mensuelle globale'),
                    ('SALAIRE_FIXE', 'Salaire fixe négocié'),
                ],
                default='',
                help_text='Origine des heures ou du montant utilisé pour calculer le salaire',
                max_length=24,
                verbose_name='Source du calcul',
            ),
        ),
        migrations.AlterField(
            model_name='enseignant',
            name='heures_mensuelles',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Volume indicatif du contrat. Le salaire réel utilise les pointages ou la saisie globale de la période.',
                max_digits=6,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0')),
                    django.core.validators.MaxValueValidator(Decimal('200')),
                ],
                verbose_name='Volume mensuel indicatif',
            ),
        ),
        migrations.AlterField(
            model_name='enseignant',
            name='salaire_fixe',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Montant mensuel négocié pour garderie, maternelle, primaire et cadres/administrateurs',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
                verbose_name='Salaire fixe (GNF)',
            ),
        ),
        migrations.AlterField(
            model_name='enseignant',
            name='type_enseignant',
            field=models.CharField(
                choices=[
                    ('GARDERIE', 'Garderie'),
                    ('MATERNELLE', 'Maternelle'),
                    ('PRIMAIRE', 'Primaire'),
                    ('SECONDAIRE', 'Secondaire (taux horaire)'),
                    ('ADMINISTRATEUR', 'Cadre / Administrateur'),
                ],
                max_length=20,
                verbose_name="Type d'enseignant",
            ),
        ),
        migrations.CreateModel(
            name='SaisieHeuresMensuelles',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('sync_uuid', models.UUIDField(db_index=True, default=uuid.uuid4, editable=False, unique=True)),
                ('sync_created_at', models.DateTimeField(auto_now_add=True)),
                ('sync_updated_at', models.DateTimeField(auto_now=True)),
                ('sync_deleted_at', models.DateTimeField(blank=True, null=True)),
                ('sync_version', models.PositiveIntegerField(default=1)),
                ('is_synced', models.BooleanField(db_index=True, default=False)),
                ('heures', models.DecimalField(
                    decimal_places=2,
                    max_digits=6,
                    validators=[
                        django.core.validators.MinValueValidator(Decimal('0')),
                        django.core.validators.MaxValueValidator(Decimal('744')),
                    ],
                    verbose_name='Heures mensuelles réalisées',
                )),
                ('date_creation', models.DateTimeField(auto_now_add=True)),
                ('date_modification', models.DateTimeField(auto_now=True)),
                ('enseignant', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saisies_heures_mensuelles',
                    to='salaires.enseignant',
                    verbose_name='Enseignant',
                )),
                ('periode', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='saisies_heures_mensuelles',
                    to='salaires.periodesalaire',
                    verbose_name='Période',
                )),
                ('saisi_par', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='saisies_heures_mensuelles',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Saisi par',
                )),
            ],
            options={
                'verbose_name': "Saisie mensuelle d'heures",
                'verbose_name_plural': "Saisies mensuelles d'heures",
                'ordering': ['-periode__annee', '-periode__mois', 'enseignant__nom'],
                'constraints': [models.UniqueConstraint(
                    fields=('enseignant', 'periode'),
                    name='sal_uniq_heures_ens_periode',
                )],
            },
        ),
    ]
