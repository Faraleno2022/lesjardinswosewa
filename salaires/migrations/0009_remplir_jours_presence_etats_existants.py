from calendar import monthrange
from datetime import date

from django.db import migrations


def remplir_jours_presence(apps, schema_editor):
    EtatSalaire = apps.get_model('salaires', 'EtatSalaire')
    PresenceEnseignant = apps.get_model('salaires', 'PresenceEnseignant')

    for etat in EtatSalaire.objects.select_related('periode').iterator():
        debut = date(etat.periode.annee, etat.periode.mois, 1)
        fin = date(
            etat.periode.annee,
            etat.periode.mois,
            monthrange(etat.periode.annee, etat.periode.mois)[1],
        )
        jours = (
            PresenceEnseignant.objects.filter(
                enseignant_id=etat.enseignant_id,
                date__range=(debut, fin),
                statut__in=('PRESENT', 'RETARD'),
            )
            .values('date')
            .distinct()
            .count()
        )
        EtatSalaire.objects.filter(pk=etat.pk).update(
            nombre_jours_presence=jours
        )


class Migration(migrations.Migration):

    dependencies = [
        ('salaires', '0008_jours_presence_etat_salaire'),
    ]

    operations = [
        migrations.RunPython(
            remplir_jours_presence,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
