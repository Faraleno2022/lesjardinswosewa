import unicodedata
from decimal import Decimal

import django.core.validators
from django.db import migrations, models


def categoriser_types(apps, schema_editor):
    TypePaiement = apps.get_model('paiements', 'TypePaiement')
    for type_paiement in TypePaiement.objects.all().iterator():
        label = unicodedata.normalize(
            'NFKD', (type_paiement.nom or '').lower()
        )
        label = ''.join(char for char in label if not unicodedata.combining(char))
        compact = ''.join(
            char for char in label
            if char.isalnum()
        )
        if 'cantine' in compact or 'restauration' in compact:
            categorie = 'CANTINE'
        elif 'transport' in compact or 'bus' in compact:
            categorie = 'TRANSPORT'
        elif any(word in compact for word in ('fourniture', 'livre', 'cahier')):
            categorie = 'FOURNITURES'
        elif 'uniforme' in compact or 'tenue' in compact:
            categorie = 'UNIFORME'
        elif any(word in compact for word in ('activite', 'sortie', 'excursion')):
            categorie = 'ACTIVITES'
        elif any(
            word in compact
            for word in ('scolar', 'inscription', 'reinscription', 'tranche', 'annuel')
        ):
            categorie = 'SCOLARITE'
        else:
            categorie = 'AUTRE'
        TypePaiement.objects.filter(pk=type_paiement.pk).update(categorie=categorie)


class Migration(migrations.Migration):

    dependencies = [
        ('paiements', '0014_isoler_paiements_par_annee'),
    ]

    operations = [
        migrations.AddField(
            model_name='typepaiement',
            name='categorie',
            field=models.CharField(
                choices=[
                    ('AUTO', 'Détection automatique (compatibilité)'),
                    ('SCOLARITE', 'Scolarité / inscription'),
                    ('CANTINE', 'Cantine'),
                    ('TRANSPORT', 'Transport / bus'),
                    ('FOURNITURES', 'Fournitures scolaires'),
                    ('UNIFORME', 'Uniforme'),
                    ('ACTIVITES', 'Activités'),
                    ('AUTRE', 'Autre'),
                ],
                db_index=True,
                default='AUTO',
                help_text="Seuls les types de catégorie Scolarité alimentent l'échéancier des frais scolaires.",
                max_length=20,
                verbose_name='Catégorie comptable',
            ),
        ),
        migrations.RunPython(categoriser_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='remisereduction',
            name='valeur',
            field=models.DecimalField(
                decimal_places=2,
                help_text='Pourcentage (ex: 10.50) ou montant en GNF',
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
                verbose_name='Valeur',
            ),
        ),
        migrations.AlterField(
            model_name='paiementremise',
            name='montant_remise',
            field=models.DecimalField(
                decimal_places=0,
                max_digits=10,
                validators=[django.core.validators.MinValueValidator(Decimal('0'))],
                verbose_name='Montant de la remise (GNF)',
            ),
        ),
        migrations.AddConstraint(
            model_name='remisereduction',
            constraint=models.CheckConstraint(
                condition=models.Q(('valeur__gte', 0)),
                name='remise_reduction_valeur_non_negative',
            ),
        ),
        migrations.AddConstraint(
            model_name='paiementremise',
            constraint=models.CheckConstraint(
                condition=models.Q(('montant_remise__gte', 0)),
                name='paiement_remise_montant_non_negatif',
            ),
        ),
    ]
