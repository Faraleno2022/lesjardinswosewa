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


def _document_last_key(payment, discounts):
    """Dernier poste explicitement couvert par le libellé du reçu remisé."""
    if not discounts:
        return None
    from .calculs import normaliser_libelle

    label = normaliser_libelle(
        getattr(getattr(payment, "type_paiement", None), "nom", "")
    )
    compact = "".join(label.split())
    if "annuel" in compact or "tranche3" in compact:
        return "tranche_3"
    if "tranche2" in compact:
        return "tranche_2"
    if "tranche1" in compact:
        return "tranche_1"
    return None


def build_document_payment_allocation_history(echeancier, payments):
    """Reconstruit l'affectation nette présentée sur les documents.

    Cette fonction ne modifie ni le paiement ni l'échéancier. Le montant brut
    encaissé reste disponible dans les totaux comptables, tandis que les
    colonnes Inscription/T1/T2/T3 ne répètent jamais une remise.
    """
    balances = due_balances(echeancier)
    allocations = {}

    for payment in payments:
        manager = getattr(payment, "remises", None)
        discounts = list(manager.all()) if manager is not None else []
        _, discounted_balances = allocate_discounts(
            echeancier, discounts, balances=balances
        )

        last_key = _document_last_key(payment, discounts)
        allocation_balances = dict(discounted_balances)
        if last_key is not None:
            last_index = ALLOCATION_KEYS.index(last_key)
            for key in ALLOCATION_KEYS[last_index + 1:]:
                # Le reçu n'annonçait pas ces tranches : une remise sur la
                # dernière tranche citée ne doit pas y créer un faux paiement.
                allocation_balances[key] = Decimal("0")

        allocation, _, _ = allocate_amount_sequentially(
            getattr(payment, "montant", 0), allocation_balances
        )
        balances = {
            key: max(Decimal("0"), discounted_balances[key] - allocation[key])
            for key in ALLOCATION_KEYS
        }
        allocations[payment.pk] = allocation

    return allocations, balances


def allocate_discounts(echeancier, discounts, balances=None):
    """Ventile les remises validées sur les tranches réellement concernées.

    Les remises ne couvrent jamais l'inscription/réinscription. Les anciennes
    remises sans information de tranche sont appliquées à T1, T2 puis T3 afin
    de rester compatibles avec les données antérieures.
    """
    current_balances = dict(balances or remaining_balances(echeancier))
    allocation = {key: Decimal('0') for key in ALLOCATION_KEYS}

    for discount in discounts:
        selected = [
            f"tranche_{number}"
            for number in getattr(discount, 'tranches_concernees_liste', [])
            if number in (1, 2, 3)
        ]
        if not selected:
            selected = ['tranche_1', 'tranche_2', 'tranche_3']

        amount = max(Decimal('0'), as_decimal(getattr(discount, 'montant_remise', 0)))
        for key in selected:
            if amount <= 0:
                break
            available = max(Decimal('0'), as_decimal(current_balances.get(key, 0)))
            take = min(amount, available)
            allocation[key] += take
            current_balances[key] = available - take
            amount -= take

    return allocation, current_balances
