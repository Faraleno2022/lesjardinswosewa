"""Règles de calcul du moteur de paie.

Les enseignants au forfait sont payés au prorata de leur date d'embauche.
Les enseignants du secondaire sont payés sur les heures réellement pointées
pendant la période. Les affectations servent à ventiler ces heures par classe.
"""

from calendar import monthrange
from datetime import date
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q, Sum

from .models import (
    AvanceSalaire,
    DetailHeuresClasse,
    Enseignant,
    EtatSalaire,
    JOURS_EMPLOI_DU_TEMPS,
    ParametresPaie,
    PeriodeSalaire,
    SaisieHeuresMensuelles,
    SourceHeuresSalaire,
    StatutAvanceSalaire,
)


HEURE = Decimal('0.01')
MONTANT = Decimal('0.01')
STATUTS_HEURES_PAYEES = ('PRESENT', 'RETARD', 'PERMISSION')


def arrondir_heures(valeur):
    return Decimal(str(valeur or 0)).quantize(HEURE, rounding=ROUND_HALF_UP)


def arrondir_montant(valeur):
    return Decimal(str(valeur or 0)).quantize(MONTANT, rounding=ROUND_HALF_UP)


def bornes_periode(periode):
    premier_jour = date(periode.annee, periode.mois, 1)
    dernier_jour = date(
        periode.annee,
        periode.mois,
        monthrange(periode.annee, periode.mois)[1],
    )
    return premier_jour, dernier_jour


def enseignants_eligibles(periode):
    """Enseignants actifs déjà embauchés à la fin de la période."""
    _, dernier_jour = bornes_periode(periode)
    return Enseignant.objects.filter(
        ecole=periode.ecole,
        statut='ACTIF',
        date_embauche__lte=dernier_jour,
    ).order_by('nom', 'prenoms')


def heures_reellement_travaillees(enseignant, periode):
    premier_jour, dernier_jour = bornes_periode(periode)
    total = enseignant.presences.filter(
        date__range=(premier_jour, dernier_jour),
        statut__in=STATUTS_HEURES_PAYEES,
    ).aggregate(total=Sum('heures_travaillees'))['total']
    return arrondir_heures(total)


def nombre_jours_presence(enseignant, periode):
    """Compte les jours de présence effective, quel que soit le mode de paie."""
    premier_jour, dernier_jour = bornes_periode(periode)
    return (
        enseignant.presences.filter(
            date__range=(premier_jour, dernier_jour),
            statut__in=('PRESENT', 'RETARD'),
        )
        .values('date')
        .distinct()
        .count()
    )


def occurrences_jours_semaine(periode):
    """Nombre de lundis, mardis... du mois, indexé par ``weekday()``."""
    premier_jour, dernier_jour = bornes_periode(periode)
    occurrences = [0] * 7
    for jour in range(premier_jour.day, dernier_jour.day + 1):
        occurrences[date(periode.annee, periode.mois, jour).weekday()] += 1
    return occurrences


def heures_emploi_du_temps(enseignant, periode):
    """Heures à prester du mois selon l'emploi du temps hebdomadaire."""
    occurrences = occurrences_jours_semaine(periode)
    return arrondir_heures(sum(
        (
            (getattr(enseignant, champ) or Decimal('0')) * occurrences[jour]
            for champ, _, jour in JOURS_EMPLOI_DU_TEMPS
        ),
        Decimal('0'),
    ))


def heures_payables_et_source(enseignant, periode, heures_absence=Decimal('0')):
    """Retourne les heures à payer et leur source explicite.

    Ordre de priorité : pointages journaliers, saisie mensuelle globale, puis
    emploi du temps hebdomadaire diminué des heures d'absence du mois.
    """
    heures_pointage = heures_reellement_travaillees(enseignant, periode)
    if heures_pointage > 0:
        return heures_pointage, SourceHeuresSalaire.POINTAGE

    saisie = SaisieHeuresMensuelles.objects.filter(
        enseignant=enseignant,
        periode=periode,
    ).first()
    if saisie is not None:
        return arrondir_heures(saisie.heures), SourceHeuresSalaire.SAISIE_MENSUELLE

    if enseignant.heures_hebdomadaires > 0:
        a_prester = heures_emploi_du_temps(enseignant, periode)
        return (
            max(Decimal('0'), a_prester - arrondir_heures(heures_absence)),
            SourceHeuresSalaire.EMPLOI_DU_TEMPS,
        )
    return heures_pointage, SourceHeuresSalaire.POINTAGE


def annees_anciennete(enseignant, periode):
    """Années de service comptées comme dans l'état Excel : année - embauche."""
    return max(0, periode.annee - enseignant.date_embauche.year)


def appliquer_primes_et_retenues(etat, parametres=None):
    """Recalcule les rubriques automatiques d'un état sans toucher aux saisies.

    La prime de fonction vient de la fiche du personnel ; la prime de craie
    ajoute au montant fixe de la fiche l'effectif du mois × le taux par élève ;
    ancienneté, éloignement, professeur principal, révision et jours chômés
    sont valorisés avec le barème de l'école. Performance et prime
    exceptionnelle restent des saisies du mois.
    """
    enseignant = etat.enseignant
    if parametres is None:
        parametres = ParametresPaie.pour_ecole(etat.periode.ecole)

    etat.prime_fonction = arrondir_montant(enseignant.prime_fonction)
    etat.prime_craie = arrondir_montant(
        (enseignant.prime_craie or Decimal('0'))
        + (etat.effectif_eleves or 0) * parametres.prime_craie_par_eleve
    )
    etat.prime_anciennete = arrondir_montant(
        annees_anciennete(enseignant, etat.periode)
        * parametres.prime_anciennete_par_an
    )
    etat.prime_eloignement = arrondir_montant(
        (enseignant.distance_km or Decimal('0'))
        * parametres.prime_eloignement_par_km
    )
    etat.prime_professeur_principal = arrondir_montant(
        (etat.classes_professeur_principal or 0)
        * parametres.prime_professeur_principal
    )
    etat.prime_revision = arrondir_montant(
        (etat.heures_revision or Decimal('0')) * parametres.prime_heure_revision
    )
    etat.retenue_jours_chomes = arrondir_montant(
        (etat.jours_chomes or 0) * parametres.retenue_par_jour_chome
    )


def affectations_de_la_periode(enseignant, periode):
    """Affectations dont les dates chevauchent la période de paie.

    Une affectation clôturée reste utilisable pour un calcul historique.
    Une affectation désactivée sans date de fin est ignorée.
    """
    premier_jour, dernier_jour = bornes_periode(periode)
    return (
        enseignant.affectations
        .filter(date_debut__lte=dernier_jour)
        .filter(Q(date_fin__isnull=True) | Q(date_fin__gte=premier_jour))
        .filter(Q(actif=True) | Q(date_fin__isnull=False))
        .select_related('classe')
        .order_by('classe__nom', 'id')
    )


def heures_prevues_par_affectation(enseignant, periode):
    premier_jour, dernier_jour = bornes_periode(periode)
    jours_periode = Decimal((dernier_jour - premier_jour).days + 1)
    lignes = []

    for affectation in affectations_de_la_periode(enseignant, periode):
        debut = max(premier_jour, affectation.date_debut)
        fin = min(dernier_jour, affectation.date_fin or dernier_jour)
        jours_couverts = Decimal((fin - debut).days + 1)
        prorata = jours_couverts / jours_periode
        heures_prevues = (
            (affectation.heures_par_semaine or Decimal('0'))
            * periode.nombre_semaines
            * prorata
        )
        lignes.append((affectation, heures_prevues))

    return lignes


def repartir_heures(total_heures, lignes_prevues):
    """Répartit les centièmes d'heure sans perte ni durée négative.

    Après arrondi inférieur des parts proportionnelles, les centièmes restants
    vont aux plus grands restes. Une affectation de poids nul reste à zéro.
    """
    total_heures = max(Decimal("0"), arrondir_heures(total_heures))
    lignes_prevues = list(lignes_prevues)
    poids = [max(Decimal("0"), Decimal(str(h))) for _, h in lignes_prevues]
    total_prevu = sum(poids, Decimal("0"))
    if not lignes_prevues or total_prevu <= 0:
        return []

    parts = [total_heures * h / total_prevu for h in poids]
    heures = [part.quantize(HEURE, rounding=ROUND_DOWN) for part in parts]
    centiemes = int((total_heures - sum(heures, Decimal("0"))) / HEURE)
    ordre = sorted(
        (i for i, h in enumerate(poids) if h > 0),
        key=lambda i: parts[i] - heures[i], reverse=True,
    )
    for i in ordre[:centiemes]:
        heures[i] += HEURE
    return [
        (affectation, arrondir_heures(prevues), heures[i])
        for i, (affectation, prevues) in enumerate(lignes_prevues)
    ]


def synchroniser_details_heures(etat):
    """Met à jour la ventilation d'un état horaire sans effacer son historique."""
    lignes_prevues = heures_prevues_par_affectation(etat.enseignant, etat.periode)
    repartition = repartir_heures(etat.total_heures or 0, lignes_prevues)
    affectations_courantes = set()

    for affectation, heures_prevues, heures_realisees in repartition:
        affectations_courantes.add(affectation.pk)
        DetailHeuresClasse.objects.update_or_create(
            etat_salaire=etat,
            affectation_classe=affectation,
            defaults={
                'heures_prevues': heures_prevues,
                'heures_realisees': heures_realisees,
                'taux_horaire_applique': etat.taux_horaire_applique or Decimal('0'),
            },
        )

    # Les anciennes ventilations sont conservées pour l'audit, mais neutralisées.
    anciens_details = etat.details_heures.all()
    if affectations_courantes:
        anciens_details = anciens_details.exclude(
            affectation_classe_id__in=affectations_courantes
        )
    for detail in anciens_details:
        detail.heures_prevues = Decimal('0')
        detail.heures_realisees = Decimal('0')
        detail.taux_horaire_applique = etat.taux_horaire_applique or Decimal('0')
        detail.save()


def salaire_fixe_proratise(enseignant, periode):
    premier_jour, dernier_jour = bornes_periode(periode)
    if enseignant.date_embauche > dernier_jour:
        return Decimal('0.00')

    premier_jour_paye = max(premier_jour, enseignant.date_embauche)
    jours_payes = Decimal((dernier_jour - premier_jour_paye).days + 1)
    jours_periode = Decimal((dernier_jour - premier_jour).days + 1)
    return arrondir_montant(
        (enseignant.salaire_fixe or Decimal('0')) * jours_payes / jours_periode
    )


def total_avances_a_deduire(enseignant, periode):
    """Total des avances actives à récupérer sur la période."""
    total = AvanceSalaire.objects.filter(
        enseignant=enseignant,
        periode=periode,
        statut=StatutAvanceSalaire.EN_ATTENTE,
    ).aggregate(total=Sum('montant'))['total']
    return arrondir_montant(total)


@transaction.atomic
def actualiser_avances_etat(enseignant, periode):
    """Répercute immédiatement les avances sur un état encore modifiable."""
    etat = EtatSalaire.objects.select_for_update().filter(
        enseignant=enseignant,
        periode=periode,
        valide=False,
        paye=False,
    ).first()
    if etat is None:
        return None
    etat.avances = total_avances_a_deduire(enseignant, periode)
    etat.save()
    return etat


@transaction.atomic
def calculer_etat_salaire(enseignant, periode, utilisateur):
    """Crée ou recalcule un état non validé et retourne ``(etat, modifie)``."""
    etat, _ = EtatSalaire.objects.select_for_update().get_or_create(
        enseignant=enseignant,
        periode=periode,
        defaults={
            'calcule_par': utilisateur,
            'salaire_base': Decimal('0'),
            'salaire_net': Decimal('0'),
            'avances': Decimal('0'),
        },
    )

    if etat.valide:
        return etat, False

    etat.avances = total_avances_a_deduire(enseignant, periode)
    etat.nombre_jours_presence = nombre_jours_presence(enseignant, periode)
    appliquer_primes_et_retenues(etat)

    if enseignant.est_taux_horaire:
        total_heures, source_heures = heures_payables_et_source(
            enseignant, periode, etat.heures_absence
        )
        taux_horaire = enseignant.taux_horaire or Decimal('0')
        etat.heures_a_prester = (
            heures_emploi_du_temps(enseignant, periode)
            if enseignant.heures_hebdomadaires > 0
            else None
        )
        etat.total_heures = total_heures
        etat.taux_horaire_applique = taux_horaire
        etat.source_heures = source_heures
        etat.salaire_base = arrondir_montant(total_heures * taux_horaire)
        etat.calcule_par = utilisateur
        etat.save()

        synchroniser_details_heures(etat)
    else:
        etat.total_heures = None
        etat.taux_horaire_applique = None
        etat.heures_a_prester = None
        etat.source_heures = SourceHeuresSalaire.SALAIRE_FIXE
        etat.salaire_base = salaire_fixe_proratise(enseignant, periode)
        etat.calcule_par = utilisateur
        etat.save()

    return etat, True


@transaction.atomic
def preparer_etats_salaire_periode(periode, utilisateur):
    """Regroupe et calcule les états de tous les enseignants d'une période.

    Le même service est utilisé à la création de la période et lors d'un
    recalcul manuel. Les états validés restent intacts ; aucun état existant
    n'est supprimé définitivement.
    """
    enseignants = list(
        enseignants_eligibles(periode).select_for_update()
    )
    calculs_effectues = 0

    for enseignant in enseignants:
        _, modifie = calculer_etat_salaire(
            enseignant, periode, utilisateur
        )
        calculs_effectues += int(modifie)

    return {
        'enseignants': len(enseignants),
        'etats_calcules': calculs_effectues,
    }


def etats_par_categorie(periode, categorie=None):
    """États de la période regroupés comme dans le classeur de paie.

    Retourne une liste de groupes ``{'categorie', 'libelle', 'etats',
    'totaux'}`` dans l'ordre Direction, Primaire, Secondaire, Appui ; les
    groupes vides sont omis.
    """
    from .models import CategoriePaie

    etats = (
        EtatSalaire.objects.filter(periode=periode)
        .select_related('enseignant')
        .order_by('enseignant__nom', 'enseignant__prenoms')
    )
    groupes = []
    for code, libelle in CategoriePaie.choices:
        if categorie and code != categorie:
            continue
        lignes = [e for e in etats if e.enseignant.categorie_paie == code]
        if not lignes:
            continue
        groupes.append({
            'categorie': code,
            'libelle': libelle,
            'etats': lignes,
            'totaux': totaux_etats(lignes),
        })
    return groupes


def totaux_etats(etats):
    etats = list(etats)
    zero = Decimal('0')
    totaux = {
        'effectif': len(etats),
        'salaire_base': sum((e.salaire_base or zero for e in etats), zero),
        'primes': sum((e.primes or zero for e in etats), zero),
        'brut': sum((e.salaire_brut for e in etats), zero),
        'retenues': sum((e.total_retenues for e in etats), zero),
        'avances': sum((e.avances or zero for e in etats), zero),
        'net': sum((e.salaire_net or zero for e in etats), zero),
    }
    for champ in EtatSalaire.CHAMPS_PRIMES:
        totaux[champ] = sum((getattr(e, champ) or zero for e in etats), zero)
    return totaux


def recalculer_etat_salaire_pour_date(enseignant, date_pointage, utilisateur):
    """Recalcule le brouillon de salaire du mois après un pointage."""
    periode = PeriodeSalaire.objects.filter(
        ecole=enseignant.ecole,
        mois=date_pointage.month,
        annee=date_pointage.year,
        cloturee=False,
    ).first()
    if periode is None:
        return None, False

    etat_existant = EtatSalaire.objects.filter(
        enseignant=enseignant,
        periode=periode,
    ).first()
    if etat_existant is not None and etat_existant.valide:
        return etat_existant, False

    return calculer_etat_salaire(enseignant, periode, utilisateur)
