"""Répartition individuelle des élèves importés entre classes d'un même niveau."""
from collections import defaultdict
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import HttpResponseBadRequest
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from utilisateurs.permissions import has_permission
from utilisateurs.utils import filter_by_user_school
from paiements.calculs import filtre_types_scolarite
from paiements.models import Paiement
from .models import Classe, Eleve


@login_required
@never_cache
@require_http_methods(['GET', 'POST'])
def repartir_eleves(request):
    autorise = (
        has_permission(request.user, 'peut_importer_eleves')
        or request.user.is_staff
        or request.user.groups.filter(name__in=['Administrateurs', 'Directeurs', 'Comptables']).exists()
    )
    if not autorise:
        raise PermissionDenied
    base = filter_by_user_school(
        Eleve.objects.filter(est_dans_corbeille=False), request.user, 'classe__ecole',
    )
    retour = reverse('eleves:repartir_eleves')
    if request.GET:
        retour += '?' + request.GET.urlencode()
    if request.method == 'POST':
        if getattr(getattr(request.user, 'profil', None), 'lecture_seule', False):
            raise PermissionDenied
        if request.POST.get('action') not in ('enregistrer', 'payer'):
            return HttpResponseBadRequest('Action inconnue.')
        if any(not str(request.POST.get(k, '')).isdigit() for k in ('eleve_id', 'classe_id', 'ancienne_classe_id')):
            return HttpResponseBadRequest('Identifiant manquant ou incorrect.')
        try:
            eleve_id = int(request.POST.get('eleve_id', ''))
            classe_id = int(request.POST.get('classe_id', ''))
        except (TypeError, ValueError):
            return HttpResponseBadRequest('Élève ou classe invalide.')
        with transaction.atomic():
            eleve = get_object_or_404(base.select_for_update(), pk=eleve_id)
            if str(eleve.classe_id) != request.POST.get('ancienne_classe_id'):
                messages.error(request, "La classe de cet élève a déjà changé. Vérifiez sa nouvelle affectation.")
                return redirect(retour)
            classe = get_object_or_404(Classe, pk=classe_id,
                ecole_id=eleve.classe.ecole_id, niveau=eleve.classe.niveau,
                annee_scolaire=eleve.classe.annee_scolaire)
            if eleve.classe_id != classe.pk:
                eleve.classe = classe
                eleve._current_user = request.user
                # Utiliser le transfert métier : historique, notes et tarifs.
                eleve.save()
        messages.success(request, f"{eleve.nom_complet} affecté à {classe.nom}.")
        if request.POST['action'] == 'payer':
            paiement = Paiement.objects.filter(
                eleve=eleve, annee_scolaire=classe.annee_scolaire, statut='EN_ATTENTE',
            ).filter(filtre_types_scolarite()).order_by('date_creation', 'pk').first()
            url = (reverse('paiements:detail_paiement', args=[paiement.pk]) if paiement
                   else reverse('paiements:ajouter_paiement_eleve', args=[eleve.pk]))
            return redirect(url + '?' + urlencode({'next': retour}))
        return redirect(retour)

    import_ids = request.session.get('dernier_import_eleves', [])
    dernier_import = bool(import_ids) and request.GET.get('tous') != '1'
    eleves = base.filter(pk__in=import_ids) if dernier_import else base
    recherche = request.GET.get('q', '').strip()
    if recherche:
        eleves = eleves.filter(Q(nom__icontains=recherche) | Q(prenom__icontains=recherche)
                              | Q(matricule__icontains=recherche))
    if request.GET.get('attente') == '1':
        eleves = eleves.filter(statut='EN_ATTENTE')
    versements = Paiement.objects.filter(eleve_id=OuterRef('pk'),
        annee_scolaire=OuterRef('classe__annee_scolaire'), statut='VALIDE',
        montant__gt=0).filter(filtre_types_scolarite())
    eleves = eleves.annotate(premier_paiement_valide=Exists(versements)).select_related('classe', 'classe__ecole').order_by('nom', 'prenom', 'pk')
    page = Paginator(eleves, 40).get_page(request.GET.get('page'))
    groupes = defaultdict(list)
    classes = filter_by_user_school(Classe.objects.all(), request.user)
    scopes = Q(pk__in=[])
    for eleve in page:
        scopes |= Q(ecole_id=eleve.classe.ecole_id, niveau=eleve.classe.niveau,
                    annee_scolaire=eleve.classe.annee_scolaire)
    for classe in classes.filter(scopes).order_by('nom', 'pk'):
        groupes[(classe.ecole_id, classe.niveau, classe.annee_scolaire)].append(classe)
    for eleve in page:
        eleve.classes_repartition = groupes[(eleve.classe.ecole_id, eleve.classe.niveau, eleve.classe.annee_scolaire)]
    params = request.GET.copy()
    params.pop('page', None)
    return render(request, 'eleves/repartir_eleves.html', {
        'page_obj': page, 'dernier_import': dernier_import,
        'recherche': recherche, 'pagination_query': params.urlencode(),
    })
