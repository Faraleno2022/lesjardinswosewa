from decimal import Decimal


ALLOCATION_KEYS = ("inscription", "tranche_1", "tranche_2", "tranche_3")


def as_decimal(value):
    """Convertit une valeur monétaire en Decimal sans passer par un float."""
    return Decimal(str(value or 0))


def remaining_balances(echeancier):
    """Retourne le reste disponible pour chaque poste de l'échéancier."""
    return {
        "inscription": max(
            Decimal("0"),
            as_decimal(echeancier.frais_inscription_du)
            - as_decimal(echeancier.frais_inscription_paye),
        ),
        "tranche_1": max(
            Decimal("0"),
            as_decimal(echeancier.tranche_1_due)
            - as_decimal(echeancier.tranche_1_payee),
        ),
        "tranche_2": max(
            Decimal("0"),
            as_decimal(echeancier.tranche_2_due)
            - as_decimal(echeancier.tranche_2_payee),
        ),
        "tranche_3": max(
            Decimal("0"),
            as_decimal(echeancier.tranche_3_due)
            - as_decimal(echeancier.tranche_3_payee),
        ),
    }


def due_balances(echeancier):
    """Retourne les montants dus, utilisés pour reconstruire un historique."""
    return {
        "inscription": max(Decimal("0"), as_decimal(echeancier.frais_inscription_du)),
        "tranche_1": max(Decimal("0"), as_decimal(echeancier.tranche_1_due)),
        "tranche_2": max(Decimal("0"), as_decimal(echeancier.tranche_2_due)),
        "tranche_3": max(Decimal("0"), as_decimal(echeancier.tranche_3_due)),
    }


def allocate_amount_sequentially(amount, balances):
    """Ventile un montant: inscription, T1, T2 puis T3.

    ``balances`` contient le reste disponible par poste. La fonction ne modifie
    pas le dictionnaire reçu et retourne ``(affectation, nouveaux_restes,
    non_affecte)``. Aucun poste ne peut dépasser son montant dû.
    """
    remaining_amount = max(Decimal("0"), as_decimal(amount))
    new_balances = {
        key: max(Decimal("0"), as_decimal(balances.get(key, 0)))
        for key in ALLOCATION_KEYS
    }
    allocation = {key: Decimal("0") for key in ALLOCATION_KEYS}

    for key in ALLOCATION_KEYS:
        if remaining_amount <= 0:
            break
        take = min(remaining_amount, new_balances[key])
        if take > 0:
            allocation[key] = take
            new_balances[key] -= take
            remaining_amount -= take

    return allocation, new_balances, remaining_amount


def build_payment_allocation_history(echeancier, payments):
    """Reconstruit l'affectation de chaque paiement validé dans l'ordre."""
    balances = due_balances(echeancier)
    allocations = {}

    for payment in payments:
        allocation, balances, _ = allocate_amount_sequentially(
            getattr(payment, "montant", 0), balances
        )
        allocations[payment.pk] = allocation

    return allocations, balances
