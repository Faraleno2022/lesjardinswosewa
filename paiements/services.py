"""Services de calcul faisant autorité pour un échéancier de scolarité."""

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from .allocation import allocate_amount_sequentially, allocate_discounts, due_balances
from .calculs import filtre_types_scolarite
from .models import Paiement, PaiementRemise


def calculer_situation_echeancier(echeancier, date_reference=None, date_limite=None):
    """Calcule cash, remises, reste, exigible et retard par poste.

    ``date_limite`` permet un état historique : seuls les paiements et remises
    enregistrés au plus tard à cette date sont pris en compte. Une échéance du
    jour n'est en retard que le lendemain (comparaison strictement ``<``).
    """
    date_reference = date_reference or date.today()
    paiements = Paiement.objects.filter(
        eleve_id=echeancier.eleve_id,
        annee_scolaire=echeancier.annee_scolaire,
        statut='VALIDE',
    ).filter(filtre_types_scolarite())
    remises = PaiementRemise.objects.filter(
        paiement__eleve_id=echeancier.eleve_id,
        paiement__annee_scolaire=echeancier.annee_scolaire,
        paiement__statut='VALIDE',
    ).filter(filtre_types_scolarite('paiement__type_paiement'))
    if date_limite is not None:
        paiements = paiements.filter(date_paiement__lte=date_limite)
        remises = remises.filter(paiement__date_paiement__lte=date_limite)

    cash_total = paiements.aggregate(total=Sum('montant'))['total'] or Decimal('0')
    if date_limite is None:
        # Compatibilité avec les soldes importés avant la création des objets
        # Paiement : en temps réel, ne jamais faire disparaître un encaissement
        # historique déjà enregistré sur l'échéancier.
        cash_total = max(
            Decimal(str(cash_total)),
            Decimal(str(echeancier.total_paye or 0)),
        )
    cash_allocation, balances_after_cash, _ = allocate_amount_sequentially(
        cash_total, due_balances(echeancier)
    )
    remises = remises.select_related('paiement').order_by(
        'paiement__date_paiement', 'paiement_id', 'id'
    )
    discount_allocation, net_balances = allocate_discounts(
        echeancier, remises, balances=balances_after_cash
    )

    dates = {
        'inscription': echeancier.date_echeance_inscription,
        'tranche_1': echeancier.date_echeance_tranche_1,
        'tranche_2': echeancier.date_echeance_tranche_2,
        'tranche_3': echeancier.date_echeance_tranche_3,
    }
    dues = due_balances(echeancier)
    exigible = sum(
        (dues[key] for key, echeance in dates.items()
         if echeance and echeance < date_reference),
        Decimal('0'),
    )
    retard = sum(
        (net_balances[key] for key, echeance in dates.items()
         if echeance and echeance < date_reference),
        Decimal('0'),
    )
    return {
        'total_du': sum(dues.values(), Decimal('0')),
        'encaisse': sum(cash_allocation.values(), Decimal('0')),
        'remises': sum(discount_allocation.values(), Decimal('0')),
        'reste': sum(net_balances.values(), Decimal('0')),
        'exigible': exigible,
        'retard': retard,
        'cash_allocation': cash_allocation,
        'discount_allocation': discount_allocation,
        'restes_par_poste': net_balances,
    }
