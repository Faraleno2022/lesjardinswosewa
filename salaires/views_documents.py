"""Barème des primes, variables du mois et documents de paie d'une période."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render

from ecole_moderne.security_decorators import require_school_object
from eleves.models import Ecole
from utilisateurs.utils import user_is_admin, user_school

from . import documents
from .forms import (
    CHAMPS_VARIABLES_MOIS,
    CHAMPS_VARIABLES_SECONDAIRE,
    ParametresPaieForm,
    VariablesPaiePeriodeForm,
)
from .lettres import montant_en_lettres
from .models import CategoriePaie, ParametresPaie, PeriodeSalaire
from .services import (
    appliquer_primes_et_retenues,
    calculer_etat_salaire,
    etats_par_categorie,
    totaux_etats,
)


def _ecole_parametres(request):
    """École dont on édite le barème : celle de l'utilisateur, ou ``?ecole=``."""
    ecole = user_school(request.user)
    if user_is_admin(request.user) and request.GET.get('ecole'):
        ecole = get_object_or_404(Ecole, pk=request.GET['ecole'])
    return ecole


@login_required
def parametres_paie(request):
    ecole = _ecole_parametres(request)
    if ecole is None:
        ecoles = Ecole.objects.order_by('nom') if user_is_admin(request.user) else []
        return render(request, 'salaires/parametres_paie.html', {'ecoles': ecoles})

    parametres = ParametresPaie.pour_ecole(ecole)
    form = ParametresPaieForm(request.POST or None, instance=parametres)
    if request.method == 'POST' and form.is_valid():
        parametres = form.save(commit=False)
        parametres.modifie_par = request.user
        parametres.save()
        messages.success(
            request,
            "Barème enregistré. Recalculez les salaires des périodes ouvertes "
            "pour l'appliquer.",
        )
        url = redirect('salaires:parametres_paie').url
        if request.GET.get('ecole'):
            url += f"?ecole={ecole.pk}"
        return redirect(url)

    return render(request, 'salaires/parametres_paie.html', {
        'form': form,
        'ecole': ecole,
        'ecoles': Ecole.objects.order_by('nom') if user_is_admin(request.user) else [],
    })


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def variables_paie_periode(request, periode_id):
    """Saisie groupée : jours chômés, primes du mois, heures du secondaire."""
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    etats = [
        etat
        for groupe in etats_par_categorie(periode)
        for etat in groupe['etats']
    ]
    form = VariablesPaiePeriodeForm(request.POST or None, etats=etats)

    if request.method == 'POST':
        if periode.cloturee:
            messages.error(request, "Une période clôturée ne peut plus être modifiée.")
            return redirect('salaires:variables_paie_periode', periode_id=periode.pk)
        if form.is_valid():
            erreurs = []
            modifies = 0
            with transaction.atomic():
                for etat in etats:
                    if etat.valide or etat.paye:
                        continue
                    valeurs = form.valeurs(etat)
                    if all(getattr(etat, champ) == valeur for champ, valeur in valeurs.items()):
                        continue
                    for champ, valeur in valeurs.items():
                        setattr(etat, champ, valeur)
                    try:
                        with transaction.atomic():
                            # Le recalcul complet applique aussi les absences
                            # aux heures de l'emploi du temps.
                            appliquer_primes_et_retenues(etat)
                            etat.save()
                            calculer_etat_salaire(etat.enseignant, periode, request.user)
                    except ValidationError as exc:
                        erreurs.append(f"{etat.enseignant.nom_complet} : {' '.join(exc.messages)}")
                    else:
                        modifies += 1
            if erreurs:
                for erreur in erreurs:
                    messages.error(request, erreur)
            messages.success(request, f"{modifies} état(s) de salaire mis à jour.")
            return redirect('salaires:variables_paie_periode', periode_id=periode.pk)

    lignes = []
    for etat in etats:
        champs = [
            form[form.nom_champ(etat, champ)]
            for champ in (*CHAMPS_VARIABLES_MOIS, *CHAMPS_VARIABLES_SECONDAIRE)
            if form.nom_champ(etat, champ) in form.fields
        ]
        lignes.append({'etat': etat, 'champs': champs})
    return render(request, 'salaires/variables_paie.html', {
        'periode': periode,
        'form': form,
        'lignes': lignes,
    })


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def documents_periode(request, periode_id):
    """Masse salariale de la période et accès aux documents imprimables."""
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    groupes = etats_par_categorie(periode)
    total = totaux_etats(e for g in groupes for e in g['etats'])
    return render(request, 'salaires/documents_paie.html', {
        'periode': periode,
        'groupes': groupes,
        'total': total,
        'total_en_lettres': montant_en_lettres(total['brut']),
        'categories': CategoriePaie.choices,
    })


def _categorie(request):
    categorie = request.GET.get('categorie') or None
    if categorie and categorie not in CategoriePaie.values:
        raise Http404("Catégorie inconnue")
    return categorie


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def pdf_etat_salaire(request, periode_id):
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    return documents.pdf_etat_salaire(periode, _categorie(request))


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def pdf_masse_salariale(request, periode_id):
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    return documents.pdf_masse_salariale(periode)


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def pdf_emargement(request, periode_id):
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    return documents.pdf_emargement(periode, _categorie(request))


@login_required
@require_school_object(model=PeriodeSalaire, pk_kwarg='periode_id', field_path='ecole')
def pdf_acomptes(request, periode_id):
    periode = get_object_or_404(PeriodeSalaire.objects.select_related('ecole'), pk=periode_id)
    return documents.pdf_acomptes(periode)
