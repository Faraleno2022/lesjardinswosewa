import unicodedata

from django.db import migrations, models


def _payment_preference(type_name):
    normalized = unicodedata.normalize("NFKD", (type_name or "").strip().lower())
    compact = "".join(
        char for char in normalized
        if not unicodedata.combining(char) and char.isalnum()
    )
    if "reinscription" in compact:
        return "REINSCRIPTION"
    if "inscription" in compact:
        return "INSCRIPTION"
    return None


def classify_existing_schedules(apps, schema_editor):
    Echeancier = apps.get_model("paiements", "EcheancierPaiement")
    Paiement = apps.get_model("paiements", "Paiement")
    Grille = apps.get_model("eleves", "GrilleTarifaire")

    schedules = Echeancier.objects.select_related("eleve__classe").all()
    for schedule in schedules.iterator():
        nature = None

        # Un type explicitement choisi par l'utilisateur est la source la plus
        # fiable. Les paiements validés sont prioritaires, puis les autres.
        for validated_only in (True, False):
            payments = Paiement.objects.filter(eleve_id=schedule.eleve_id)
            if validated_only:
                payments = payments.filter(statut="VALIDE")
            else:
                payments = payments.exclude(statut="VALIDE")
            payments = payments.select_related("type_paiement").order_by(
                "date_paiement", "date_creation", "id"
            )
            for payment in payments.iterator():
                nature = _payment_preference(payment.type_paiement.nom)
                if nature:
                    break
            if nature:
                break

        # Pour les anciennes données sans paiement d'admission, le montant de
        # la grille permet une classification seulement si les deux tarifs
        # sont différents. En cas d'égalité, on garde le défaut Inscription.
        if nature is None:
            classe = getattr(schedule.eleve, "classe", None)
            if classe:
                grid = Grille.objects.filter(
                    ecole_id=classe.ecole_id,
                    niveau=classe.niveau,
                    annee_scolaire=schedule.annee_scolaire,
                ).first()
                if grid and grid.frais_inscription != grid.frais_reinscription:
                    if schedule.frais_inscription_du == grid.frais_reinscription:
                        nature = "REINSCRIPTION"
                    elif schedule.frais_inscription_du == grid.frais_inscription:
                        nature = "INSCRIPTION"

        if nature and schedule.nature_frais != nature:
            Echeancier.objects.filter(pk=schedule.pk).update(nature_frais=nature)


class Migration(migrations.Migration):

    dependencies = [
        ("eleves", "0016_ecole_bonus_suivi_actif"),
        ("paiements", "0009_complete_sync_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="echeancierpaiement",
            name="nature_frais",
            field=models.CharField(
                choices=[
                    ("INSCRIPTION", "Inscription"),
                    ("REINSCRIPTION", "Réinscription"),
                ],
                db_index=True,
                default="INSCRIPTION",
                max_length=20,
                verbose_name="Nature du frais d'admission",
            ),
        ),
        migrations.RunPython(classify_existing_schedules, migrations.RunPython.noop),
    ]
