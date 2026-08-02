from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from eleves.models import Classe, Eleve
from eleves.utils_annee import get_annee_active
from utilisateurs.utils import filter_by_user_school, user_is_superadmin, user_school

from .forms import BienEtablissementForm, ContributionPapierRamForm
from .models_logistique import BienEtablissement, ContributionPapierRam


def _annee_logistique(request, ecole=None):
    annee = request.GET.get('annee') or request.POST.get('annee_scolaire')
    if annee:
        return annee
    if ecole:
        return get_annee_active(request, ecole)
    return (
        Classe.objects.order_by('-annee_scolaire')
        .values_list('annee_scolaire', flat=True)
        .first()
    )


def _biens_visibles(user, actifs_seulement=True):
    biens = BienEtablissement.objects.select_related('ecole', 'cree_par')
    if actifs_seulement:
        biens = biens.filter(actif=True)
    if user_is_superadmin(user):
        return biens
    ecole = user_school(user)
    if not ecole:
        return biens.none()
    # Le second filtre conserve l'accès aux anciens biens créés avant l'ajout
    # du champ école. Ils seront rattachés lors de leur prochaine modification.
    return biens.filter(
        Q(ecole=ecole) | Q(ecole__isnull=True, cree_par__profil__ecole=ecole)
    )


def _contributions_visibles(user):
    contributions = ContributionPapierRam.objects.select_related(
        'ecole', 'eleve', 'eleve__classe', 'cree_par'
    )
    return filter_by_user_school(contributions, user, 'ecole')


def _eleves_visibles(user, ecole, annee):
    eleves = Eleve.objects.select_related('classe', 'classe__ecole').filter(statut='ACTIF')
    if not user_is_superadmin(user):
        if not ecole:
            return eleves.none()
        eleves = eleves.filter(classe__ecole=ecole)
    if annee:
        eleves = eleves.filter(classe__annee_scolaire=annee)
    return eleves


def _resume_biens(biens):
    valeur_expression = ExpressionWrapper(
        F('quantite_achetee') * F('prix_achat_unitaire'),
        output_field=DecimalField(max_digits=20, decimal_places=0),
    )
    resume = biens.aggregate(
        total_quantite_achetee=Sum('quantite_achetee'),
        total_quantite_utilisee=Sum('quantite_utilisee'),
        total_quantite_gatee=Sum('quantite_gatee'),
        valeur_totale=Sum(valeur_expression),
    )
    achetee = resume['total_quantite_achetee'] or 0
    utilisee = resume['total_quantite_utilisee'] or 0
    gatee = resume['total_quantite_gatee'] or 0
    return {
        'total_biens': biens.count(),
        'quantite_achetee': achetee,
        'quantite_utilisee': utilisee,
        'quantite_gatee': gatee,
        'quantite_disponible': max(0, achetee - utilisee - gatee),
        'valeur_totale': resume['valeur_totale'] or Decimal('0'),
    }


def _resume_ram(contributions, eleves):
    papier = contributions.filter(mode_contribution='PAPIER')
    argent = contributions.filter(mode_contribution='ARGENT')
    total_enregistres = contributions.values('eleve_id').distinct().count()
    return {
        'total_eleves': eleves.count(),
        'total_enregistres': total_enregistres,
        'total_en_attente': max(0, eleves.count() - total_enregistres),
        'eleves_papier': papier.values('eleve_id').distinct().count(),
        'paquets_recus': papier.aggregate(total=Sum('nombre_paquets'))['total'] or 0,
        'eleves_argent': argent.values('eleve_id').distinct().count(),
        'montant_recu': argent.aggregate(total=Sum('montant_paye'))['total'] or Decimal('0'),
    }


@login_required
def dashboard_logistique(request):
    """Tableau de bord unifié : biens de l'école et contributions papier RAM."""
    ecole = user_school(request.user)
    annee = _annee_logistique(request, ecole)
    biens = _biens_visibles(request.user)
    contributions = _contributions_visibles(request.user)
    if annee:
        contributions = contributions.filter(annee_scolaire=annee)
    eleves = _eleves_visibles(request.user, ecole, annee)
    eleves_enregistres = contributions.values_list('eleve_id', flat=True)

    context = {
        'titre_page': 'Logistique simplifiée',
        'annee_active': annee,
        'resume_biens': _resume_biens(biens),
        'resume_ram': _resume_ram(contributions, eleves),
        'derniers_biens': biens.order_by('-date_creation')[:8],
        'dernieres_contributions': contributions.order_by('-date_contribution', '-date_creation')[:8],
        'eleves_en_attente': eleves.exclude(pk__in=eleves_enregistres).order_by('classe__nom', 'nom', 'prenom')[:8],
    }
    return render(request, 'depenses/logistique/dashboard.html', context)


@login_required
def liste_biens(request):
    q = request.GET.get('q', '').strip()
    type_bien = request.GET.get('type_bien', '').strip()
    biens = _biens_visibles(request.user)
    if q:
        biens = biens.filter(
            Q(code_bien__icontains=q)
            | Q(nom__icontains=q)
            | Q(marque__icontains=q)
            | Q(localisation__icontains=q)
        )
    if type_bien:
        biens = biens.filter(type_bien=type_bien)
    context = {
        'titre_page': "Biens de l'établissement",
        'biens': biens.order_by('nom'),
        'resume_biens': _resume_biens(biens),
        'types_biens': BienEtablissement.TYPE_CHOICES,
        'q': q,
        'type_bien': type_bien,
    }
    return render(request, 'depenses/logistique/liste_biens.html', context)


def _generer_code_bien():
    prefixe = f"BIEN-{date.today():%Y%m%d}"
    dernier = BienEtablissement.objects.filter(code_bien__startswith=prefixe).order_by('-code_bien').first()
    try:
        numero = int(dernier.code_bien.rsplit('-', 1)[1]) + 1 if dernier else 1
    except (ValueError, IndexError):
        numero = 1
    return f"{prefixe}-{numero:04d}"


@login_required
def creer_bien(request):
    ecole = user_school(request.user)
    form = BienEtablissementForm(request.POST or None, ecole=ecole)
    if request.method == 'POST' and form.is_valid():
        bien = form.save(commit=False)
        if ecole:
            bien.ecole = ecole
        bien.cree_par = request.user
        if not bien.code_bien:
            bien.code_bien = _generer_code_bien()
        bien.valeur_acquisition = bien.valeur_totale_achat
        bien.save()
        messages.success(request, f'Le bien « {bien.nom} » a été ajouté.')
        return redirect('depenses:liste_biens')
    return render(request, 'depenses/logistique/form_bien.html', {
        'titre_page': 'Ajouter un bien',
        'form': form,
    })


@login_required
def modifier_bien(request, bien_id):
    bien = get_object_or_404(_biens_visibles(request.user, actifs_seulement=False), pk=bien_id)
    ecole = user_school(request.user)
    form = BienEtablissementForm(request.POST or None, instance=bien, ecole=ecole)
    if request.method == 'POST' and form.is_valid():
        bien = form.save(commit=False)
        if ecole:
            bien.ecole = ecole
        bien.valeur_acquisition = bien.valeur_totale_achat
        bien.save()
        messages.success(request, f'Le bien « {bien.nom} » a été mis à jour.')
        return redirect('depenses:liste_biens')
    return render(request, 'depenses/logistique/form_bien.html', {
        'titre_page': 'Modifier un bien',
        'form': form,
        'bien': bien,
    })


@login_required
@require_POST
def archiver_bien(request, bien_id):
    bien = get_object_or_404(_biens_visibles(request.user), pk=bien_id)
    bien.actif = False
    bien.save(update_fields=['actif'])
    messages.success(request, f'Le bien « {bien.nom} » a été archivé.')
    return redirect('depenses:liste_biens')


@login_required
def gestion_papier_ram(request):
    ecole = user_school(request.user)
    annee = _annee_logistique(request, ecole)
    q = request.GET.get('q', '').strip()
    mode = request.GET.get('mode', '').strip()
    contributions = _contributions_visibles(request.user)
    if annee:
        contributions = contributions.filter(annee_scolaire=annee)
    contributions_resume = contributions
    if q:
        contributions = contributions.filter(
            Q(eleve__matricule__icontains=q)
            | Q(eleve__nom__icontains=q)
            | Q(eleve__prenom__icontains=q)
            | Q(eleve__classe__nom__icontains=q)
        )
    if mode:
        contributions = contributions.filter(mode_contribution=mode)
    eleves = _eleves_visibles(request.user, ecole, annee)
    annees = Classe.objects.values_list('annee_scolaire', flat=True).distinct().order_by('-annee_scolaire')
    if ecole and not user_is_superadmin(request.user):
        annees = annees.filter(ecole=ecole)
    context = {
        'titre_page': 'Gestion du papier RAM',
        'contributions': contributions.order_by('eleve__classe__nom', 'eleve__nom', 'eleve__prenom'),
        'resume_ram': _resume_ram(contributions_resume, eleves),
        'annees': annees,
        'annee_active': annee,
        'q': q,
        'mode': mode,
    }
    return render(request, 'depenses/logistique/papier_ram_liste.html', context)


@login_required
def ajouter_papier_ram(request):
    ecole = user_school(request.user)
    annee = _annee_logistique(request, ecole)
    form = ContributionPapierRamForm(
        request.POST or None,
        ecole=ecole,
        annee_scolaire=annee,
        initial={'annee_scolaire': annee, 'mode_contribution': 'PAPIER', 'date_contribution': date.today()},
    )
    if request.method == 'POST' and form.is_valid():
        contribution = form.save(commit=False)
        ecole_eleve = contribution.eleve.classe.ecole
        if ecole and ecole_eleve.pk != ecole.pk:
            form.add_error('eleve', "Cet élève n'appartient pas à votre établissement.")
        elif ContributionPapierRam.objects.filter(
            ecole=ecole_eleve,
            eleve=contribution.eleve,
            annee_scolaire=contribution.annee_scolaire,
        ).exists():
            form.add_error('eleve', "Une contribution existe déjà pour cet élève et cette année.")
        else:
            contribution.ecole = ecole_eleve
            contribution.cree_par = request.user
            contribution.save()
            messages.success(request, f'Contribution de {contribution.eleve.nom_complet} enregistrée.')
            return redirect('depenses:gestion_papier_ram')
    return render(request, 'depenses/logistique/papier_ram_form.html', {
        'titre_page': 'Enregistrer une contribution RAM',
        'form': form,
    })


@login_required
def modifier_papier_ram(request, contribution_id):
    contribution = get_object_or_404(_contributions_visibles(request.user), pk=contribution_id)
    ecole = user_school(request.user)
    form = ContributionPapierRamForm(
        request.POST or None,
        instance=contribution,
        ecole=ecole,
        annee_scolaire=contribution.annee_scolaire,
    )
    if request.method == 'POST' and form.is_valid():
        modifiee = form.save(commit=False)
        ecole_eleve = modifiee.eleve.classe.ecole
        doublon = ContributionPapierRam.objects.filter(
            ecole=ecole_eleve,
            eleve=modifiee.eleve,
            annee_scolaire=modifiee.annee_scolaire,
        ).exclude(pk=contribution.pk)
        if ecole and ecole_eleve.pk != ecole.pk:
            form.add_error('eleve', "Cet élève n'appartient pas à votre établissement.")
        elif doublon.exists():
            form.add_error('eleve', "Une contribution existe déjà pour cet élève et cette année.")
        else:
            modifiee.ecole = ecole_eleve
            modifiee.save()
            messages.success(request, 'Contribution RAM mise à jour.')
            return redirect('depenses:gestion_papier_ram')
    return render(request, 'depenses/logistique/papier_ram_form.html', {
        'titre_page': 'Modifier la contribution RAM',
        'form': form,
        'contribution': contribution,
    })


@login_required
@require_POST
def supprimer_papier_ram(request, contribution_id):
    contribution = get_object_or_404(_contributions_visibles(request.user), pk=contribution_id)
    contribution.delete()
    messages.success(request, 'Contribution RAM supprimée.')
    return redirect('depenses:gestion_papier_ram')
