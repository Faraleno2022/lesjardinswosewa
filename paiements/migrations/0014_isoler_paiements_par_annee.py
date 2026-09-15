from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def renseigner_annee_paiements(apps, schema_editor):
    Paiement = apps.get_model('paiements', 'Paiement')
    Echeancier = apps.get_model('paiements', 'EcheancierPaiement')

    for paiement in Paiement.objects.filter(annee_scolaire='').iterator():
        echeancier = Echeancier.objects.filter(
            eleve_id=paiement.eleve_id
        ).order_by('-annee_scolaire').first()
        annee = getattr(echeancier, 'annee_scolaire', '') or ''
        if not annee:
            eleve = paiement.eleve
            annee = getattr(getattr(eleve, 'classe', None), 'annee_scolaire', '') or ''
        paiement.annee_scolaire = annee
        paiement.save(update_fields=['annee_scolaire'])


def retour_annee_paiements(apps, schema_editor):
    Paiement = apps.get_model('paiements', 'Paiement')
    Paiement.objects.update(annee_scolaire='')


class Migration(migrations.Migration):

    dependencies = [
        ('paiements', '0013_historiquemodificationpaiement'),
    ]

    operations = [
        migrations.AddField(
            model_name='paiement',
            name='annee_scolaire',
            field=models.CharField(blank=True, db_index=True, default='', max_length=9, verbose_name='Année scolaire'),
            preserve_default=False,
        ),
        migrations.RunPython(renseigner_annee_paiements, retour_annee_paiements),
        migrations.AlterField(
            model_name='paiement',
            name='annee_scolaire',
            field=models.CharField(
                db_index=True,
                max_length=9,
                validators=[
                    django.core.validators.RegexValidator(
                        message="L'année scolaire doit être au format AAAA-AAAA.",
                        regex='^\\d{4}-\\d{4}$',
                    )
                ],
                verbose_name='Année scolaire',
            ),
        ),
        migrations.AlterField(
            model_name='paiement',
            name='montant',
            field=models.DecimalField(
                decimal_places=0,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('1'))],
                verbose_name='Montant (GNF)',
            ),
        ),
        migrations.AddConstraint(
            model_name='paiement',
            constraint=models.CheckConstraint(
                condition=models.Q(('montant__gt', 0)),
                name='paiement_montant_strictement_positif',
            ),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='eleve',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='echeanciers',
                to='eleves.eleve',
            ),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='annee_scolaire',
            field=models.CharField(
                max_length=9,
                validators=[
                    django.core.validators.RegexValidator(
                        message="L'année scolaire doit être au format AAAA-AAAA.",
                        regex='^\\d{4}-\\d{4}$',
                    )
                ],
                verbose_name='Année scolaire',
            ),
        ),
        migrations.AddConstraint(
            model_name='echeancierpaiement',
            constraint=models.UniqueConstraint(
                fields=('eleve', 'annee_scolaire'),
                name='echeancier_unique_eleve_annee',
            ),
        ),
        migrations.AddConstraint(
            model_name='echeancierpaiement',
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(('frais_inscription_du__gte', 0))
                    & models.Q(('tranche_1_due__gte', 0))
                    & models.Q(('tranche_2_due__gte', 0))
                    & models.Q(('tranche_3_due__gte', 0))
                    & models.Q(('frais_inscription_paye__gte', 0))
                    & models.Q(('tranche_1_payee__gte', 0))
                    & models.Q(('tranche_2_payee__gte', 0))
                    & models.Q(('tranche_3_payee__gte', 0))
                ),
                name='echeancier_montants_non_negatifs',
            ),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='frais_inscription_du',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name="Frais d'inscription dus (GNF)"),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='frais_inscription_paye',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name="Frais d'inscription payés (GNF)"),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_1_due',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='1ère tranche due (GNF)'),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_1_payee',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='1ère tranche payée (GNF)'),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_2_due',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='2ème tranche due (GNF)'),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_2_payee',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='2ème tranche payée (GNF)'),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_3_due',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='3ème tranche due (GNF)'),
        ),
        migrations.AlterField(
            model_name='echeancierpaiement',
            name='tranche_3_payee',
            field=models.DecimalField(decimal_places=0, default=Decimal('0'), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0'))], verbose_name='3ème tranche payée (GNF)'),
        ),
    ]
