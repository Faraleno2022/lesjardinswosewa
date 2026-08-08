"""Renseigne depuis la grille tarifaire les échéanciers restés entièrement vides.

Un échéancier créé avant la saisie de la grille tarifaire de son niveau/année
(ou lors d'un passage d'année sans grille) garde tous ses montants dus à 0.
L'élève apparaît alors comme ne devant rien, et aucun paiement ne peut être
enregistré tant que l'échéancier n'est pas rechargé.

C'est notamment le cas après avoir corrigé le niveau des classes avec
`corriger_niveaux_maternelle` : la grille devient enfin trouvable, mais les
échéanciers déjà créés restent vides.

    python manage.py remplir_echeanciers_vides              # simulation
    python manage.py remplir_echeanciers_vides --appliquer  # applique
"""
from django.core.management.base import BaseCommand

from eleves.models import Eleve


class Command(BaseCommand):
    help = (
        "Renseigne depuis la grille tarifaire les échéanciers dont tous les "
        "montants dus valent 0 (élèves qui ne peuvent plus payer)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Applique réellement les changements (sans ce drapeau : simulation seule).",
        )
        parser.add_argument(
            '--ecole', type=str, default=None,
            help="Limiter à une école (nom exact ou partiel).",
        )
        parser.add_argument(
            '--annee', type=str, default=None,
            help="Limiter à une année scolaire de classe (ex: 2026-2027).",
        )

    def handle(self, *args, **options):
        # Import tardif : `ensure_echeancier_for_eleve` vit dans les vues paiements.
        from paiements.views import ensure_echeancier_for_eleve

        appliquer = options['appliquer']

        eleves = (
            Eleve.objects
            .filter(statut='ACTIF')
            .select_related('classe', 'classe__ecole', 'echeancier')
        )
        if options['ecole']:
            eleves = eleves.filter(classe__ecole__nom__icontains=options['ecole'])
        if options['annee']:
            eleves = eleves.filter(classe__annee_scolaire=options['annee'])

        eleves = eleves.order_by('classe__ecole__nom', 'classe__nom', 'nom', 'prenom')

        vides = []
        for eleve in eleves:
            ech = getattr(eleve, 'echeancier', None)
            if ech is None:
                continue  # sera créé au besoin par le flux normal
            total = int(
                (ech.frais_inscription_du or 0) + (ech.tranche_1_due or 0)
                + (ech.tranche_2_due or 0) + (ech.tranche_3_due or 0)
            )
            if total <= 0:
                vides.append(eleve)

        if not vides:
            self.stdout.write(self.style.SUCCESS("Aucun échéancier vide : rien à faire."))
            return

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING(
            f"{len(vides)} échéancier(s) vide(s) détecté(s) :"
        ))

        remplis = 0
        toujours_vides = []
        for eleve in vides:
            classe = eleve.classe
            libelle = (
                f"{classe.ecole.nom} | {classe.annee_scolaire} | {classe.nom} | "
                f"{eleve.matricule} {eleve.nom_complet}"
            )
            if not appliquer:
                self.stdout.write(f"  {libelle}")
                continue

            try:
                ech = ensure_echeancier_for_eleve(eleve)
                total = int(
                    (ech.frais_inscription_du or 0) + (ech.tranche_1_due or 0)
                    + (ech.tranche_2_due or 0) + (ech.tranche_3_due or 0)
                ) if ech else 0
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"  ÉCHEC {libelle} : {exc}"))
                toujours_vides.append(eleve)
                continue

            if total > 0:
                remplis += 1
                self.stdout.write(self.style.SUCCESS(f"  OK {libelle} -> {total:,} GNF".replace(',', ' ')))
            else:
                toujours_vides.append(eleve)
                self.stdout.write(self.style.WARNING(f"  VIDE {libelle} (aucune grille applicable)"))

        self.stdout.write("")
        if not appliquer:
            self.stdout.write(self.style.WARNING(
                f"Simulation : {len(vides)} échéancier(s) seraient rechargé(s). "
                "Relancez avec --appliquer pour enregistrer."
            ))
            return

        self.stdout.write(self.style.SUCCESS(f"{remplis} échéancier(s) renseigné(s)."))
        if toujours_vides:
            self.stdout.write(self.style.WARNING(
                f"{len(toujours_vides)} échéancier(s) restent vides : il n'existe aucune "
                "grille tarifaire pour le niveau et l'année scolaire de leur classe. "
                "Créez la grille manquante, puis relancez cette commande."
            ))
