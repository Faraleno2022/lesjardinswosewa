"""Abonnements d'un élève : liste, exports PDF / Excel et carnet."""

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from eleves.models import Eleve
from utilisateurs.utils import filter_by_user_school

from . import historique


def _eleve_autorise(request, eleve_id):
    eleves = filter_by_user_school(
        Eleve.objects.filter(est_dans_corbeille=False).select_related(
            'classe', 'classe__ecole', 'responsable_principal'
        ),
        request.user,
        'classe__ecole',
    )
    return get_object_or_404(eleves, pk=eleve_id)


def _type_demande(request):
    type_abonnement = request.GET.get('type') or None
    if type_abonnement and type_abonnement not in historique.TYPES_ABONNEMENT:
        raise Http404("Type d'abonnement inconnu")
    return type_abonnement


@login_required
def abonnements_eleve(request, eleve_id):
    eleve = _eleve_autorise(request, eleve_id)
    type_abonnement = _type_demande(request)
    lignes = historique.lignes_abonnements(eleve, type_abonnement)
    return render(request, 'bus/abonnements_eleve.html', {
        'eleve': eleve,
        'lignes': list(reversed(lignes)),
        'total': historique.total_montants(lignes),
        'type_abonnement': type_abonnement or '',
        'types': historique.LIBELLES_TYPES.items(),
    })


@login_required
def abonnements_eleve_excel(request, eleve_id):
    eleve = _eleve_autorise(request, eleve_id)
    lignes = historique.lignes_abonnements(eleve, _type_demande(request))
    return historique.export_excel(eleve, lignes)


@login_required
def abonnements_eleve_pdf(request, eleve_id):
    eleve = _eleve_autorise(request, eleve_id)
    type_abonnement = _type_demande(request)
    lignes = historique.lignes_abonnements(eleve, type_abonnement)
    return historique.export_pdf(
        eleve, lignes, libelle_type=historique.LIBELLES_TYPES.get(type_abonnement, ''),
    )


@login_required
def carnet_abonnement_pdf(request, eleve_id):
    eleve = _eleve_autorise(request, eleve_id)
    type_abonnement = _type_demande(request)
    lignes = historique.lignes_abonnements(eleve, type_abonnement)
    return historique.export_pdf(
        eleve, lignes, carnet=True,
        libelle_type=historique.LIBELLES_TYPES.get(type_abonnement, ''),
    )
