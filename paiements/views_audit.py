"""Journal global des modifications et suppressions douces de paiements."""

from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone

from utilisateurs.utils import filter_by_user_school

from .models import HistoriqueModificationPaiement


PERIODES = {
    'jour': "Aujourd'hui",
    'semaine': 'Cette semaine',
    'mois': 'Ce mois',
    'annee': 'Cette année',
    'tout': 'Tout l’historique',
}


def _date_debut(periode, today):
    if periode == 'jour':
        return today
    if periode == 'semaine':
        return today - timedelta(days=today.weekday())
    if periode == 'annee':
        return today.replace(month=1, day=1)
    if periode == 'tout':
        return None
    return today.replace(day=1)


@login_required
def historique_paiements(request):
    periode = (request.GET.get('periode') or 'mois').strip().lower()
    if periode not in PERIODES:
        periode = 'mois'
    operation = (request.GET.get('operation') or '').strip().upper()
    operations_valides = {
        value for value, _label in HistoriqueModificationPaiement.Operation.choices
    }
    if operation not in operations_valides:
        operation = ''
    q = (request.GET.get('q') or '').strip()
    today = timezone.localdate()

    queryset = HistoriqueModificationPaiement.objects.select_related(
        'paiement', 'ecole', 'utilisateur'
    )
    queryset = filter_by_user_school(queryset, request.user, 'ecole')
    debut = _date_debut(periode, today)
    if debut:
        queryset = queryset.filter(
            date_modification__date__gte=debut,
            date_modification__date__lte=today,
        )
    if operation:
        queryset = queryset.filter(operation=operation)
    if q:
        queryset = queryset.filter(
            Q(numero_recu__icontains=q)
            | Q(eleve__icontains=q)
            | Q(motif__icontains=q)
            | Q(utilisateur__username__icontains=q)
        )

    page_obj = Paginator(queryset.order_by('-date_modification', '-id'), 30).get_page(
        request.GET.get('page')
    )
    return render(request, 'paiements/historique_operations.html', {
        'titre_page': 'Modifications et suppressions de paiements',
        'page_obj': page_obj,
        'periode': periode,
        'periodes': PERIODES,
        'operation': operation,
        'operations': HistoriqueModificationPaiement.Operation.choices,
        'q': q,
    })
