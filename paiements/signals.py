"""Maintient l'échéancier cohérent lors des écritures hors vues métier.

Les modifications effectuées depuis l'administration Django, la
synchronisation ou un script passent toutes par les modèles. Ces signaux
évitent qu'un changement de montant, de statut, de type ou de remise laisse
des champs ``*_paye`` périmés.
"""

import logging

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Paiement, PaiementRemise


logger = logging.getLogger(__name__)


def _recalculer(eleve_id, annee_scolaire):
    if not eleve_id or not annee_scolaire:
        return
    try:
        from eleves.models import Eleve
        from .views import _auto_validate_echeancier_for_eleve

        eleve = Eleve.objects.filter(pk=eleve_id).first()
        if eleve:
            _auto_validate_echeancier_for_eleve(
                eleve,
                preserve_recorded=False,
                annee_scolaire=annee_scolaire,
                strict=True,
            )
    except Exception:
        logger.exception(
            "Recalcul automatique de l'échéancier impossible pour élève=%s année=%s",
            eleve_id,
            annee_scolaire,
        )


@receiver(pre_save, sender=Paiement)
def memoriser_ancienne_portee_paiement(sender, instance, **kwargs):
    if not instance.pk:
        instance._ancienne_portee_echeancier = None
        return
    instance._ancienne_portee_echeancier = (
        sender.objects.filter(pk=instance.pk)
        .values_list('eleve_id', 'annee_scolaire')
        .first()
    )


@receiver(post_save, sender=Paiement)
def recalculer_apres_paiement(sender, instance, **kwargs):
    ancienne = getattr(instance, '_ancienne_portee_echeancier', None)
    nouvelle = (instance.eleve_id, instance.annee_scolaire)
    if ancienne and ancienne != nouvelle:
        _recalculer(*ancienne)
    _recalculer(*nouvelle)


@receiver(post_delete, sender=Paiement)
def recalculer_apres_suppression_paiement(sender, instance, **kwargs):
    _recalculer(instance.eleve_id, instance.annee_scolaire)


@receiver(post_save, sender=PaiementRemise)
@receiver(post_delete, sender=PaiementRemise)
def recalculer_apres_remise(sender, instance, **kwargs):
    try:
        paiement = instance.paiement
    except Paiement.DoesNotExist:
        return
    _recalculer(paiement.eleve_id, paiement.annee_scolaire)
