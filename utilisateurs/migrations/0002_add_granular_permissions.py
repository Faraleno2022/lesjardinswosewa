# Generated manually for granular permissions
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('utilisateurs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='profil',
            name='peut_ajouter_paiements',
            field=models.BooleanField(default=True, verbose_name='Peut ajouter des paiements'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_ajouter_depenses',
            field=models.BooleanField(default=True, verbose_name='Peut ajouter des dépenses'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_ajouter_enseignants',
            field=models.BooleanField(default=True, verbose_name='Peut ajouter des enseignants'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_modifier_paiements',
            field=models.BooleanField(default=True, verbose_name='Peut modifier les paiements'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_modifier_depenses',
            field=models.BooleanField(default=True, verbose_name='Peut modifier les dépenses'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_supprimer_paiements',
            field=models.BooleanField(default=False, verbose_name='Peut supprimer les paiements'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_supprimer_depenses',
            field=models.BooleanField(default=False, verbose_name='Peut supprimer les dépenses'),
        ),
        migrations.AddField(
            model_name='profil',
            name='peut_consulter_rapports',
            field=models.BooleanField(default=True, verbose_name='Peut consulter les rapports'),
        ),
    ]
