from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('eleves', '0010_rendre_champs_optionnels'),
    ]

    operations = [
        migrations.AddField(
            model_name='ecole',
            name='telephone2',
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                validators=[django.core.validators.RegexValidator('^\\+224\\d{8,9}$', 'Format: +224XXXXXXXXX')],
                verbose_name='Téléphone 2',
            ),
        ),
        migrations.AddField(
            model_name='ecole',
            name='telephone3',
            field=models.CharField(
                blank=True,
                max_length=20,
                null=True,
                validators=[django.core.validators.RegexValidator('^\\+224\\d{8,9}$', 'Format: +224XXXXXXXXX')],
                verbose_name='Téléphone 3',
            ),
        ),
        migrations.AlterField(
            model_name='ecole',
            name='telephone',
            field=models.CharField(
                max_length=20,
                validators=[django.core.validators.RegexValidator('^\\+224\\d{8,9}$', 'Format: +224XXXXXXXXX')],
                verbose_name='Téléphone principal',
            ),
        ),
    ]
