from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notes', '0004_activitejournaliere_piecejointeactivite_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='activitejournaliere',
            name='type_activite',
            field=models.CharField(
                choices=[
                    ('ABSENCE', 'Absence'),
                    ('RETARD', 'Retard'),
                    ('DISCIPLINE', 'Discipline'),
                    ('CONVOCATION', 'Convocation parent'),
                    ('EVALUATION', 'Évaluation'),
                    ('SPORTIVE', 'Sportive'),
                    ('CULTURELLE', 'Culturelle'),
                    ('ARTISTIQUE', 'Artistique'),
                    ('SORTIE', 'Sortie éducative'),
                    ('AUTRE', 'Autre'),
                ],
                max_length=20,
                verbose_name="Type d'observation",
            ),
        ),
    ]
