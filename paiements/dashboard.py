"""Indicateurs financiers de la page d'accueil des paiements."""

from datetime import timedelta
from decimal import Decimal

from bus.models import AbonnementBus, AbonnementCantine
from django.db.models import Count, OuterRef, Subquery, Sum
from django.utils import timezone
from utilisateurs.utils import filter_by_user_school

from .calculs import (
    CATEGORIE_CANTINE,
    CATEGORIE_SCOLARITE,
    CATEGORIE_TRANSPORT,
    categorie_effective,
)
from .models import HistoriqueModificationPaiement, Paiement
from .reporting import ventiler_encaissements_par_paiement


PERIODES = (
    ('jour', "Aujourd'hui"),
    ('semaine', 'Cette semaine'),
    ('mois', 'Ce mois'),
    ('annee', 'Cette année'),
)


def _nouvelle_carte(key, label, icon, theme, retard=None):
    return {
        'key': key,
        'label': label,
        'icon': icon,
        'theme': theme,
        'periodes': [
            {'key': period_key, 'label': period_label, 'montant': 0, 'nombre': 0}
            for period_key, period_label in PERIODES
        ],
        'retard': retard,
    }


def _ajouter_aux_periodes(carte, paiement, montant, debuts, today):
    montant = Decimal(str(montant or 0))
    if montant <= 0 or paiement.date_paiement > today:
        return
    for periode in carte['periodes']:
        if paiement.date_paiement >= debuts[periode['key']]:
            periode['montant'] += montant
            periode['nombre'] += 1


def _ajouter_abonnements_aux_periodes(carte, model, user, debuts, today):
    """Ajoute les encaissements saisis directement dans Bus/Cantine.

    Ces formulaires enregistrent historiquement le montant dans le modèle
    d'abonnement, sans créer un objet ``Paiement``. Les ignorer laissait donc
    les cartes du tableau de bord à zéro alors que les abonnements existaient.
    La date de début est la date métier disponible pour rattacher l'encaissement
    aux périodes du tableau de bord.
    """
    queryset = model.objects.filter(
        date_debut__gte=min(debuts.values()),
        date_debut__lte=today,
    )
    queryset = filter_by_user_school(
        queryset, user, 'eleve__classe__ecole'
    )
    for abonnement in queryset.only('date_debut', 'montant'):
        montant = Decimal(str(abonnement.montant or 0))
        if montant <= 0:
            continue
        for periode in carte['periodes']:
            if abonnement.date_debut >= debuts[periode['key']]:
                periode['montant'] += montant
                periode['nombre'] += 1


def _resume_abonnements_expires(model, user, today):
    """Compte uniquement le dernier abonnement connu de chaque élève."""
    dernier_id = (
        model.objects.filter(eleve_id=OuterRef('eleve_id'))
        .order_by('-date_expiration', '-id')
        .values('id')[:1]
    )
    queryset = model.objects.filter(
        id=Subquery(dernier_id),
        date_expiration__lt=today,
    ).exclude(statut=model.Statut.SUSPENDU)
    queryset = filter_by_user_school(
        queryset, user, 'eleve__classe__ecole'
    )
    resume = queryset.aggregate(montant=Sum('montant'), nombre=Count('id'))
    return {
        'montant': resume['montant'] or Decimal('0'),
        'nombre': resume['nombre'] or 0,
        'libelle': 'abonnement(s) expiré(s)',
        'aide': 'Montant estimé pour renouveler les derniers abonnements',
    }


def calculer_indicateurs_audit_paiements(user, today):
    """Résume l'impact des montants modifiés et supprimés par période."""
    week_start = today - timedelta(days=today.weekday())
    debuts = {
        'jour': today,
        'semaine': week_start,
        'mois': today.replace(day=1),
        'annee': today.replace(month=1, day=1),
    }
    periodes = [
        {
            'key': key,
            'label': label,
            'modifications': 0,
            'montant_avant': Decimal('0'),
            'montant_apres': Decimal('0'),
            'variation_nette': Decimal('0'),
            'suppressions': 0,
            'montant_supprime': Decimal('0'),
        }
        for key, label in PERIODES
    ]
    queryset = HistoriqueModificationPaiement.objects.filter(
        date_modification__date__gte=debuts['annee'],
        date_modification__date__lte=today,
    )
    queryset = filter_by_user_school(queryset, user, 'ecole')
    for historique in queryset.only(
        'operation', 'champs_modifies', 'donnees_avant', 'donnees_apres',
        'date_modification',
    ):
        date_operation = timezone.localtime(historique.date_modification).date()
        est_suppression = (
            historique.operation
            == HistoriqueModificationPaiement.Operation.SUPPRESSION
        )
        est_modification_montant = (
            not est_suppression
            and 'montant' in (historique.champs_modifies or [])
            and historique.montant_avant != historique.montant_apres
        )
        if not est_suppression and not est_modification_montant:
            continue
        for periode in periodes:
            if date_operation < debuts[periode['key']]:
                continue
            if est_suppression:
                periode['suppressions'] += 1
                periode['montant_supprime'] += historique.montant_avant
            else:
                periode['modifications'] += 1
                periode['montant_avant'] += historique.montant_avant
                periode['montant_apres'] += historique.montant_apres
                periode['variation_nette'] += historique.variation_montant
    return periodes


def calculer_indicateurs_categories(user, today, retard_scolarite):
    """Calcule les encaissements validés du jour, semaine, mois et année."""
    week_start = today - timedelta(days=today.weekday())
    debuts = {
        'jour': today,
        'semaine': week_start,
        'mois': today.replace(day=1),
        'annee': today.replace(month=1, day=1),
    }
    premier_jour = min(debuts.values())

    cartes = {
        'scolarite': _nouvelle_carte(
            'scolarite',
            'Scolarité',
            'fa-graduation-cap',
            'primary',
            retard={
                'montant': Decimal(str(retard_scolarite.get('montant', 0))),
                'nombre': int(retard_scolarite.get('nombre', 0)),
                'libelle': 'élève(s) en retard',
                'aide': 'Échéances de scolarité dépassées et non réglées',
            },
        ),
        'transport': _nouvelle_carte(
            'transport',
            'Bus / Transport',
            'fa-bus',
            'info',
            retard=_resume_abonnements_expires(AbonnementBus, user, today),
        ),
        'cantine': _nouvelle_carte(
            'cantine',
            'Cantine',
            'fa-utensils',
            'warning',
            retard=_resume_abonnements_expires(AbonnementCantine, user, today),
        ),
        'inscription': _nouvelle_carte(
            'inscription',
            'Inscription',
            'fa-user-plus',
            'success',
        ),
        'reinscription': _nouvelle_carte(
            'reinscription',
            'Réinscription',
            'fa-user-check',
            'secondary',
        ),
    }

    queryset = (
        Paiement.objects.filter(
            statut='VALIDE',
            date_paiement__gte=premier_jour,
            date_paiement__lte=today,
        )
        .select_related('type_paiement')
        .order_by('date_paiement', 'date_creation', 'id')
    )
    queryset = filter_by_user_school(
        queryset, user, 'eleve__classe__ecole'
    )
    paiements = list(queryset)
    ventilations = ventiler_encaissements_par_paiement(paiements)

    _ajouter_abonnements_aux_periodes(
        cartes['transport'], AbonnementBus, user, debuts, today
    )
    _ajouter_abonnements_aux_periodes(
        cartes['cantine'], AbonnementCantine, user, debuts, today
    )

    for paiement in paiements:
        categorie = categorie_effective(paiement.type_paiement)
        if categorie == CATEGORIE_SCOLARITE:
            ventilation = ventilations[paiement.pk]
            _ajouter_aux_periodes(
                cartes['scolarite'],
                paiement,
                ventilation['scolarite'],
                debuts,
                today,
            )
            _ajouter_aux_periodes(
                cartes['inscription'],
                paiement,
                ventilation['frais_inscription'],
                debuts,
                today,
            )
            _ajouter_aux_periodes(
                cartes['reinscription'],
                paiement,
                ventilation['reinscription'],
                debuts,
                today,
            )
        elif categorie == CATEGORIE_TRANSPORT:
            _ajouter_aux_periodes(
                cartes['transport'], paiement, paiement.montant, debuts, today
            )
        elif categorie == CATEGORIE_CANTINE:
            _ajouter_aux_periodes(
                cartes['cantine'], paiement, paiement.montant, debuts, today
            )

    return list(cartes.values())
