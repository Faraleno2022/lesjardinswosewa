"""Réaligne les échéanciers existants sur les règles comptables courantes.

Sur une base déjà en service, les champs ``*_paye`` peuvent avoir été gonflés
par des encaissements qui ne relèvent pas de la scolarité (cantine, transport,
fournitures…) avant l'introduction des catégories comptables. Tant qu'aucun
paiement de l'élève n'est retouché, l'échéancier conserve ce montant : le
service de calcul ne fait jamais disparaître un encaissement historique.

Cette commande force le recalcul. Par défaut elle reste prudente ; l'option
``--reconstruire`` reconstruit les encaissements uniquement à partir des
paiements de scolarité validés, ce qui est la seule façon d'effacer une
inflation par cantine.
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F

from paiements.models import EcheancierPaiement
from paiements.views import _auto_validate_echeancier_for_eleve


CHAMPS_SUIVIS = (
    'frais_inscription_paye',
    'tranche_1_payee',
    'tranche_2_payee',
    'tranche_3_payee',
    'statut',
)


class Command(BaseCommand):
    help = (
        "Recalcule les échéanciers à partir des paiements de scolarité validés. "
        "Utiliser --dry-run d'abord, puis --reconstruire pour effacer une "
        "inflation par des encaissements hors scolarité."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help="N'écrit rien : liste seulement les échéanciers qui changeraient.",
        )
        parser.add_argument(
            '--reconstruire', action='store_true',
            help=(
                "Reconstruit les encaissements depuis les seuls paiements de "
                "scolarité validés. ATTENTION : un solde d'ouverture importé "
                "sans objet Paiement correspondant sera remis à zéro."
            ),
        )
        parser.add_argument('--ecole-id', type=int, help="Limiter à une école.")
        parser.add_argument(
            '--annee', type=str,
            help="Limiter à une année scolaire (format AAAA-AAAA).",
        )
        parser.add_argument(
            '--annee-courante', action='store_true',
            help="Limiter à l'année scolaire de la classe de chaque élève.",
        )
        parser.add_argument(
            '--limit', type=int, default=0,
            help="Nombre maximum d'échéanciers traités (0 = tous).",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get('dry_run'))
        reconstruire = bool(options.get('reconstruire'))
        limite = options.get('limit') or 0

        qs = EcheancierPaiement.objects.select_related(
            'eleve', 'eleve__classe', 'eleve__classe__ecole'
        ).order_by('eleve__classe__nom', 'eleve__nom', 'eleve__prenom')
        if options.get('ecole_id'):
            qs = qs.filter(eleve__classe__ecole_id=options['ecole_id'])
        if options.get('annee'):
            qs = qs.filter(annee_scolaire=options['annee'])
        if options.get('annee_courante'):
            qs = qs.filter(annee_scolaire=F('eleve__classe__annee_scolaire'))
        if limite > 0:
            qs = qs[:limite]

        echeanciers = list(qs)
        self.stdout.write(self.style.NOTICE(
            f"{len(echeanciers)} échéancier(s) à examiner. "
            f"Dry-run={dry_run} Reconstruire={reconstruire}"
        ))
        if reconstruire and not dry_run:
            self.stdout.write(self.style.WARNING(
                "Mode reconstruction : les encaissements sans objet Paiement "
                "seront perdus. Une sauvegarde préalable est recommandée."
            ))

        modifies = 0
        erreurs = 0
        for echeancier in echeanciers:
            avant = {
                champ: getattr(echeancier, champ) for champ in CHAMPS_SUIVIS
            }
            try:
                with transaction.atomic():
                    _auto_validate_echeancier_for_eleve(
                        echeancier.eleve,
                        preserve_recorded=not reconstruire,
                        annee_scolaire=echeancier.annee_scolaire,
                        strict=True,
                    )
                    echeancier.refresh_from_db()
                    apres = {
                        champ: getattr(echeancier, champ) for champ in CHAMPS_SUIVIS
                    }
                    change = avant != apres
                    if change:
                        modifies += 1
                        self.stdout.write(self._decrire(echeancier, avant, apres))
                    if dry_run:
                        transaction.set_rollback(True)
            except Exception as exc:
                erreurs += 1
                self.stderr.write(self.style.ERROR(
                    f"Échec sur {self._libelle(echeancier)} : {exc}"
                ))

        resume = (
            f"{modifies} échéancier(s) "
            f"{'à corriger' if dry_run else 'corrigé(s)'}, {erreurs} erreur(s)."
        )
        self.stdout.write(
            self.style.ERROR(resume) if erreurs else self.style.SUCCESS(resume)
        )

    def _libelle(self, echeancier):
        eleve = echeancier.eleve
        matricule = getattr(eleve, 'matricule', '') or '?'
        nom = getattr(eleve, 'nom_complet', '') or f"élève {eleve.pk}"
        return f"{matricule} {nom} ({echeancier.annee_scolaire})"

    def _decrire(self, echeancier, avant, apres):
        details = ", ".join(
            f"{champ}: {avant[champ]} -> {apres[champ]}"
            for champ in CHAMPS_SUIVIS
            if avant[champ] != apres[champ]
        )
        return f"  {self._libelle(echeancier)} | {details}"
