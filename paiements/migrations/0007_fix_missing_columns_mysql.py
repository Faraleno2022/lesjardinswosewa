from django.db import migrations, connection

def add_columns(apps, schema_editor):
    db = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if db == "mysql":
            cursor.execute("SHOW COLUMNS FROM paiements_echeancierpaiement")
            existing = [r[0] for r in cursor.fetchall()]
            columns = {
                "frais_inscription_du": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_1_due": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_2_due": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_3_due": "decimal(10,0) NOT NULL DEFAULT 0",
                "frais_inscription_paye": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_1_payee": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_2_payee": "decimal(10,0) NOT NULL DEFAULT 0",
                "tranche_3_payee": "decimal(10,0) NOT NULL DEFAULT 0",
                "date_echeance_inscription": "date NULL",
                "date_echeance_tranche_1": "date NULL",
                "date_echeance_tranche_2": "date NULL",
                "date_echeance_tranche_3": "date NULL",
            }
            for col, definition in columns.items():
                if col not in existing:
                    cursor.execute(f"ALTER TABLE paiements_echeancierpaiement ADD COLUMN {col} {definition}")
                    print(f"Colonne ajoutee: {col}")
                else:
                    print(f"Colonne deja existante: {col}")
        else:
            print(f"DB: {db} - aucune action requise")

class Migration(migrations.Migration):

    dependencies = [
        ("paiements", "0006_echeancierpaiement_paiements_e_annee_s_aa73e4_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(add_columns, migrations.RunPython.noop),
    ]
