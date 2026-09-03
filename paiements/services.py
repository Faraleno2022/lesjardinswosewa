"""Services de calcul faisant autorité pour un échéancier de scolarité."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .allocation import allocate_amount_sequentially, allocate_discounts, due_balances
from .calculs import filtre_types_scolarite, normaliser_libelle
from .models import EcheancierPaiement, Paiement, PaiementRemise


def _situation(echeancier, cash_total, remises, date_reference, date_limite):
    """Assemble la situation d'un échéancier à partir de données déjà chargées."""
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


def calculer_situations_echeanciers(echeanciers, date_reference=None, date_limite=None):
    """Calcule la situation d'un lot d'échéanciers en deux requêtes au total.

    À utiliser dès qu'une vue parcourt plusieurs échéanciers (tableaux de bord,
    rapports de retard, exports) : la version unitaire ci-dessous délègue ici,
    il n'existe donc qu'une seule règle de calcul.

    Retourne un dictionnaire ``{echeancier.pk: situation}``.
    """
    echeanciers = list(echeanciers)
    if not echeanciers:
        return {}
    date_reference = date_reference or date.today()

    eleve_ids = {ech.eleve_id for ech in echeanciers}
    annees = {ech.annee_scolaire for ech in echeanciers}

    paiements = Paiement.objects.filter(
        eleve_id__in=eleve_ids,
        annee_scolaire__in=annees,
        statut='VALIDE',
    ).filter(filtre_types_scolarite())
    remises = PaiementRemise.objects.filter(
        paiement__eleve_id__in=eleve_ids,
        paiement__annee_scolaire__in=annees,
        paiement__statut='VALIDE',
    ).filter(filtre_types_scolarite('paiement__type_paiement'))
    if date_limite is not None:
        paiements = paiements.filter(date_paiement__lte=date_limite)
        remises = remises.filter(paiement__date_paiement__lte=date_limite)

    # Le couple (élève, année) est la clé : les lignes surnuméraires ramenées
    # par le produit des deux listes ne sont simplement jamais consultées.
    cash_par_cle = defaultdict(Decimal)
    for ligne in (
        paiements.values('eleve_id', 'annee_scolaire').annotate(total=Sum('montant'))
    ):
        cle = (ligne['eleve_id'], ligne['annee_scolaire'])
        cash_par_cle[cle] = ligne['total'] or Decimal('0')

    remises_par_cle = defaultdict(list)
    for remise in (
        remises.select_related('paiement')
        .order_by('paiement__date_paiement', 'paiement_id', 'id')
    ):
        cle = (remise.paiement.eleve_id, remise.paiement.annee_scolaire)
        remises_par_cle[cle].append(remise)

    resultats = {}
    for echeancier in echeanciers:
        cle = (echeancier.eleve_id, echeancier.annee_scolaire)
        resultats[echeancier.pk] = _situation(
            echeancier,
            cash_par_cle.get(cle, Decimal('0')),
            remises_par_cle.get(cle, []),
            date_reference,
            date_limite,
        )
    return resultats


def calculer_situation_echeancier(echeancier, date_reference=None, date_limite=None):
    """Calcule cash, remises, reste, exigible et retard par poste.

    ``date_limite`` permet un état historique : seuls les paiements et remises
    enregistrés au plus tard à cette date sont pris en compte. Une échéance du
    jour n'est en retard que le lendemain (comparaison strictement ``<``).
    """
    situations = calculer_situations_echeanciers(
        [echeancier], date_reference=date_reference, date_limite=date_limite
    )
    return situations[echeancier.pk]


def _nature_frais_transfert(eleve, annee_scolaire, *, nouvelle_annee, echeancier=None):
    """Conserve la nature existante ou la déduit des reçus de l'année."""
    if echeancier is not None:
        return echeancier.nature_frais

    paiements = (
        Paiement.objects.filter(
            eleve=eleve,
            annee_scolaire=annee_scolaire,
            statut='VALIDE',
        )
        .filter(filtre_types_scolarite())
        .select_related('type_paiement')
        .order_by('date_paiement', 'date_creation', 'pk')
    )
    for paiement in paiements.iterator():
        libelle = normaliser_libelle(paiement.type_paiement.nom)
        compact = ''.join(caractere for caractere in libelle if caractere.isalnum())
        if 'reinscription' in compact:
            return 'REINSCRIPTION'
        if 'inscription' in compact:
            return 'INSCRIPTION'
    return 'REINSCRIPTION' if nouvelle_annee else 'INSCRIPTION'


def _dates_nouvel_echeancier(grille, annee_scolaire):
    aujourd_hui = timezone.localdate()
    try:
        annee_fin = int(str(annee_scolaire).split('-')[0]) + 1
    except (TypeError, ValueError, IndexError):
        annee_fin = aujourd_hui.year + (1 if aujourd_hui.month >= 9 else 0)
    return {
        'date_echeance_inscription': (
            grille.date_echeance_inscription_defaut or aujourd_hui
        ),
        'date_echeance_tranche_1': (
            grille.date_echeance_tranche_1_defaut or date(annee_fin, 1, 15)
        ),
        'date_echeance_tranche_2': (
            grille.date_echeance_tranche_2_defaut or date(annee_fin, 3, 15)
        ),
        'date_echeance_tranche_3': (
            grille.date_echeance_tranche_3_defaut or date(annee_fin, 5, 15)
        ),
    }


def _appliquer_grille_transfert(eleve, echeancier, grille, nature_frais):
    """Applique exactement le tarif cible, garde prolongée comprise."""
    echeancier.nature_frais = nature_frais
    frais_admission = (
        grille.frais_reinscription
        if nature_frais == 'REINSCRIPTION'
        else grille.frais_inscription
    )
    echeancier.frais_inscription_du = Decimal(str(frais_admission or 0))
    tranches = (
        Decimal(str(grille.tranche_1 or 0)),
        Decimal(str(grille.tranche_2 or 0)),
        Decimal(str(grille.tranche_3 or 0)),
    )
    if getattr(eleve, 'garde_prolongee', False):
        from eleves.tarification import calculer_montants_garde_prolongee

        forfait = calculer_montants_garde_prolongee(
            getattr(eleve.classe, 'niveau', None), *tranches
        )
        if forfait is not None:
            tranches = forfait
    (
        echeancier.tranche_1_due,
        echeancier.tranche_2_due,
        echeancier.tranche_3_due,
    ) = tranches

    # Une échéance explicitement configurée sur la nouvelle grille est
    # prioritaire. Sinon, les dates personnalisées existantes sont conservées.
    for champ_echeancier, champ_grille in (
        ('date_echeance_inscription', 'date_echeance_inscription_defaut'),
        ('date_echeance_tranche_1', 'date_echeance_tranche_1_defaut'),
        ('date_echeance_tranche_2', 'date_echeance_tranche_2_defaut'),
        ('date_echeance_tranche_3', 'date_echeance_tranche_3_defaut'),
    ):
        date_configuree = getattr(grille, champ_grille, None)
        if date_configuree:
            setattr(echeancier, champ_echeancier, date_configuree)


def _synchroniser_couverture_transfert(echeancier, *, conserver_saisie_manuelle):
    """Réaffecte paiements et remises sans modifier leur historique."""
    total_valide = (
        Paiement.objects.filter(
            eleve_id=echeancier.eleve_id,
            annee_scolaire=echeancier.annee_scolaire,
            statut='VALIDE',
        )
        .filter(filtre_types_scolarite())
        .aggregate(total=Sum('montant'))['total']
        or Decimal('0')
    )
    total_saisi = Decimal(str(echeancier.total_paye or 0))
    encaissement = (
        max(total_valide, total_saisi)
        if conserver_saisie_manuelle
        else total_valide
    )
    allocation, soldes_apres_encaissement, credit = allocate_amount_sequentially(
        encaissement, due_balances(echeancier)
    )
    echeancier.frais_inscription_paye = allocation['inscription']
    echeancier.tranche_1_payee = allocation['tranche_1']
    echeancier.tranche_2_payee = allocation['tranche_2']
    echeancier.tranche_3_payee = allocation['tranche_3']

    remises = (
        PaiementRemise.objects.filter(
            paiement__eleve_id=echeancier.eleve_id,
            paiement__annee_scolaire=echeancier.annee_scolaire,
            paiement__statut='VALIDE',
        )
        .filter(filtre_types_scolarite('paiement__type_paiement'))
        .select_related('paiement')
        .order_by('paiement__date_paiement', 'paiement_id', 'pk')
    )
    allocation_remises, soldes_nets = allocate_discounts(
        echeancier, remises, balances=soldes_apres_encaissement
    )

    total_du = sum(due_balances(echeancier).values(), Decimal('0'))
    couverture = sum(allocation.values(), Decimal('0')) + sum(
        allocation_remises.values(), Decimal('0')
    )
    dates = {
        'inscription': echeancier.date_echeance_inscription,
        'tranche_1': echeancier.date_echeance_tranche_1,
        'tranche_2': echeancier.date_echeance_tranche_2,
        'tranche_3': echeancier.date_echeance_tranche_3,
    }
    aujourd_hui = timezone.localdate()
    retard = sum(
        (
            soldes_nets[poste]
            for poste, echeance in dates.items()
            if echeance and echeance < aujourd_hui
        ),
        Decimal('0'),
    )
    if total_du <= 0 or couverture >= total_du:
        echeancier.statut = 'PAYE_COMPLET'
    elif retard > 0:
        echeancier.statut = 'EN_RETARD'
    elif couverture <= 0:
        echeancier.statut = 'A_PAYER'
    else:
        echeancier.statut = 'PAYE_PARTIEL'

    return {
        'encaissements_valides': total_valide,
        'encaissements_conserves': encaissement,
        'remises_conservees': sum(allocation_remises.values(), Decimal('0')),
        'credit_non_affecte': credit,
        'solde_restant': sum(soldes_nets.values(), Decimal('0')),
    }


@transaction.atomic
def reconcilier_transfert_classe(eleve, ancienne_classe, nouvelle_classe, *, cree_par=None):
    """Recalcule l'échéancier lors d'un changement de classe.

    Dans la même année, l'échéancier existant reçoit le tarif de la nouvelle
    classe et les encaissements/remises sont réaffectés. Lors d'un changement
    d'année, l'ancien échéancier reste intact et un nouvel échéancier est créé.
    Aucun objet Paiement n'est déplacé, supprimé ou changé d'année.
    """
    from eleves.models import GrilleTarifaire

    ancienne_annee = getattr(ancienne_classe, 'annee_scolaire', '') or ''
    nouvelle_annee = getattr(nouvelle_classe, 'annee_scolaire', '') or ''
    changement_annee = ancienne_annee != nouvelle_annee
    resultat = {
        'ancienne_annee': ancienne_annee,
        'nouvelle_annee': nouvelle_annee,
        'changement_annee': changement_annee,
        'changement_ecole': ancienne_classe.ecole_id != nouvelle_classe.ecole_id,
        'echeancier_cree': False,
        'echeancier_mis_a_jour': False,
        'grille_manquante': False,
        'ancien_total_du': Decimal('0'),
        'nouveau_total_du': Decimal('0'),
        'encaissements_valides': Decimal('0'),
        'encaissements_conserves': Decimal('0'),
        'remises_conservees': Decimal('0'),
        'credit_non_affecte': Decimal('0'),
        'solde_restant': Decimal('0'),
    }

    grille = GrilleTarifaire.objects.filter(
        ecole_id=nouvelle_classe.ecole_id,
        niveau=nouvelle_classe.niveau,
        annee_scolaire=nouvelle_annee,
    ).first()
    if grille is None:
        resultat['grille_manquante'] = True
        return resultat

    ancien_echeancier = EcheancierPaiement.objects.filter(
        eleve=eleve, annee_scolaire=ancienne_annee
    ).first()
    if ancien_echeancier is not None:
        resultat['ancien_total_du'] = ancien_echeancier.total_du

    echeancier = (
        EcheancierPaiement.objects.select_for_update()
        .filter(eleve=eleve, annee_scolaire=nouvelle_annee)
        .first()
    )
    echeancier_existait = echeancier is not None
    nature = _nature_frais_transfert(
        eleve,
        nouvelle_annee,
        nouvelle_annee=changement_annee,
        echeancier=echeancier,
    )
    if echeancier is None:
        echeancier = EcheancierPaiement(
            eleve=eleve,
            annee_scolaire=nouvelle_annee,
            nature_frais=nature,
            cree_par=(
                cree_par if getattr(cree_par, 'is_authenticated', False) else None
            ),
            **_dates_nouvel_echeancier(grille, nouvelle_annee),
        )
        resultat['echeancier_cree'] = True

    _appliquer_grille_transfert(eleve, echeancier, grille, nature)
    couverture = _synchroniser_couverture_transfert(
        echeancier,
        # Les soldes importés sans objet Paiement appartiennent au nouvel
        # exercice uniquement si son échéancier existait déjà. Un échéancier
        # fraîchement créé commence naturellement à zéro.
        conserver_saisie_manuelle=echeancier_existait,
    )
    echeancier.save()

    resultat.update(couverture)
    resultat['echeancier_mis_a_jour'] = True
    resultat['nouveau_total_du'] = echeancier.total_du
    resultat['echeancier_id'] = echeancier.pk
    return resultat
