# Generated manually for teacher deletion permission

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('utilisateurs', '0008_profil_peut_supprimer_abonnements'),
    ]

    operations = [
        migrations.AddField(
            model_name='profil',
            name='peut_supprimer_enseignants_definitivement',
            field=models.BooleanField(default=False, verbose_name='Peut supprimer les enseignants définitivement'),
        ),
    ]
