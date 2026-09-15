from django.db import migrations, models
import django.db.models.deletion


def memoriser_portee_existante(apps, schema_editor):
    Paiement = apps.get_model('paiements', 'Paiement')
    lot = []
    queryset = Paiement.objects.filter(
        ecole_encaissement__isnull=True,
    ).select_related('eleve__classe')
    for paiement in queryset.iterator(chunk_size=500):
        classe = getattr(paiement.eleve, 'classe', None)
        if classe is None:
            continue
        paiement.classe_encaissement_id = classe.pk
        paiement.ecole_encaissement_id = classe.ecole_id
        lot.append(paiement)
        if len(lot) >= 500:
            Paiement.objects.bulk_update(
                lot, ['classe_encaissement', 'ecole_encaissement']
            )
            lot = []
    if lot:
        Paiement.objects.bulk_update(
            lot, ['classe_encaissement', 'ecole_encaissement']
        )


class Migration(migrations.Migration):
    dependencies = [
        ('eleves', '0019_elevecorbeille_eleve_est_dans_corbeille_and_more'),
        ('paiements', '0016_remise_deduite_du_paiement'),
    ]

    operations = [
        migrations.AddField(
            model_name='paiement',
            name='classe_encaissement',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='paiements_encaisses',
                to='eleves.classe',
                verbose_name="Classe lors de l'encaissement",
            ),
        ),
        migrations.AddField(
            model_name='paiement',
            name='ecole_encaissement',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='paiements_encaisses',
                to='eleves.ecole',
                verbose_name="École lors de l'encaissement",
            ),
        ),
        migrations.RunPython(
            memoriser_portee_existante,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name='paiement',
            index=models.Index(
                fields=['ecole_encaissement', 'date_paiement'],
                name='paiements_ecole_date_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='paiement',
            index=models.Index(
                fields=['classe_encaissement', 'date_paiement'],
                name='paiements_classe_date_idx',
            ),
        ),
    ]

