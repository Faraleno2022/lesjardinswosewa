"""Ventilation exacte des encaissements pour les rapports et tableaux de bord."""

from collections import defaultdict
from decimal import Decimal

from .allocation import build_payment_allocation_history
from .calculs import est_type_scolarite, normaliser_libelle
from .models import EcheancierPaiement, Paiement


VENTILATION_KEYS = (
    'frais_inscription',
    'reinscription',
    'scolarite',
    'autres',
)


def ventiler_encaissements_par_paiement(paiements):
    """Retourne la ventilation exacte de chaque reçu sélectionné.

    Un même reçu peut couvrir l'inscription puis une tranche de scolarité. La
    ventilation est donc reconstruite depuis tout l'historique validé de
    l'élève, mais seuls les reçus reçus en argument sont retournés.
    """
    paiements = list(paiements)
    resultat = {
        paiement.pk: {key: Decimal('0') for key in VENTILATION_KEYS}
        for paiement in paiements
    }
    groupes = defaultdict(list)
    for paiement in paiements:
        if est_type_scolarite(paiement.type_paiement):
            groupes[(paiement.eleve_id, paiement.annee_scolaire)].append(paiement)
        else:
            resultat[paiement.pk]['autres'] += Decimal(
                str(paiement.montant or 0)
            )

    eleve_ids = {cle[0] for cle in groupes}
    annees = {cle[1] for cle in groupes}
    echeanciers = {
        (ech.eleve_id, ech.annee_scolaire): ech
        for ech in EcheancierPaiement.objects.filter(
            eleve_id__in=eleve_ids, annee_scolaire__in=annees
        )
    }
    historiques = defaultdict(list)
    if eleve_ids:
        historique_qs = (
            Paiement.objects.filter(
                eleve_id__in=eleve_ids,
                annee_scolaire__in=annees,
                statut='VALIDE',
            )
            .select_related('type_paiement')
            .order_by('date_paiement', 'date_creation', 'id')
        )
        for encaissement in historique_qs:
            if est_type_scolarite(encaissement.type_paiement):
                cle = (encaissement.eleve_id, encaissement.annee_scolaire)
                historiques[cle].append(encaissement)

    for cle, selection in groupes.items():
        echeancier = echeanciers.get(cle)
        if not echeancier:
            # Repli sans double comptage pour les données historiques orphelines.
            for paiement in selection:
                montant = Decimal(str(paiement.montant or 0))
                nom = normaliser_libelle(paiement.type_paiement.nom)
                compact = ''.join(nom.split())
                if 'reinscription' in compact:
                    resultat[paiement.pk]['reinscription'] += montant
                elif (
                    'inscription' in nom
                    and 'tranche' not in nom
                    and 'annuel' not in nom
                ):
                    resultat[paiement.pk]['frais_inscription'] += montant
                else:
                    resultat[paiement.pk]['scolarite'] += montant
            continue

        historique = historiques.get(cle, [])
        allocations, _ = build_payment_allocation_history(echeancier, historique)
        admission_key = (
            'reinscription'
            if echeancier.nature_frais == 'REINSCRIPTION'
            else 'frais_inscription'
        )
        for paiement in selection:
            allocation = allocations.get(paiement.pk)
            if not allocation:
                continue
            resultat[paiement.pk][admission_key] += allocation['inscription']
            resultat[paiement.pk]['scolarite'] += (
                allocation['tranche_1']
                + allocation['tranche_2']
                + allocation['tranche_3']
            )

    return resultat


def repartir_encaissements(paiements):
    """Répartit une liste de paiements sans montant forfaitaire codé en dur.

    La ventilation inscription/tranches est reconstruite depuis l'échéancier
    annuel et l'ordre réel de tous les encaissements validés. Les catégories
    hors scolarité restent dans ``autres`` et ne gonflent jamais la scolarité.
    """
    resultat = {key: Decimal('0') for key in VENTILATION_KEYS}
    for ventilation in ventiler_encaissements_par_paiement(paiements).values():
        for key in VENTILATION_KEYS:
            resultat[key] += ventilation[key]
    return resultat
