from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count
from django.core.paginator import Paginator
from datetime import date

from eleves.models import Classe as ClasseEleve, Eleve
from utilisateurs.utils import filter_by_user_school, user_school
from .models import ClasseNote, ActiviteJournaliere, PieceJointeActivite
from .forms import ActiviteJournaliereForm, PieceJointeActiviteForm


@login_required
def liste_activites(request):
    """Liste des observations de vie scolaire avec filtres."""
    from eleves.utils_annee import get_annee_active

    ecole = user_school(request.user)
    annee_active = get_annee_active(request, ecole) if ecole else None

    # Classes disponibles
    classes_qs = filter_by_user_school(
        ClasseEleve.objects.select_related('ecole').order_by('niveau', 'nom'),
        request.user, 'ecole'
    )
    if annee_active:
        classes_qs = classes_qs.filter(annee_scolaire=annee_active)

    # Filtres
    classe_id = request.GET.get('classe')
    type_activite = request.GET.get('type')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    search = request.GET.get('q', '').strip()

    activites = ActiviteJournaliere.objects.select_related(
        'eleve', 'classe'
    ).prefetch_related('pieces_jointes')

    if ecole:
        activites = activites.filter(classe__ecole=ecole)

    if classe_id:
        activites = activites.filter(classe_id=classe_id)
    if type_activite:
        activites = activites.filter(type_activite=type_activite)
    if date_debut:
        activites = activites.filter(date__gte=date_debut)
    if date_fin:
        activites = activites.filter(date__lte=date_fin)
    if search:
        activites = activites.filter(
            Q(titre__icontains=search)
            | Q(description__icontains=search)
            | Q(appreciation__icontains=search)
            | Q(eleve__nom__icontains=search)
            | Q(eleve__prenom__icontains=search)
            | Q(eleve__matricule__icontains=search)
        )

    # Stats
    vie_scolaire_types = ['ABSENCE', 'RETARD', 'DISCIPLINE', 'CONVOCATION']
    stats_par_type = dict(
        activites.values_list('type_activite').annotate(c=Count('id')).order_by()
    )
    stats = {
        'total': activites.count(),
        'par_type': stats_par_type,
        'vie_scolaire_total': sum(int(stats_par_type.get(code, 0) or 0) for code in vie_scolaire_types),
    }

    paginator = Paginator(activites, 20)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'page_obj': page,
        'classes': classes_qs,
        'types': ActiviteJournaliere.TYPE_CHOICES,
        'stats': stats,
        'filtre_classe': classe_id,
        'filtre_type': type_activite,
        'filtre_date_debut': date_debut,
        'filtre_date_fin': date_fin,
        'filtre_search': search,
    }
    return render(request, 'notes/activites/liste.html', context)


@login_required
def ajouter_activite(request):
    """Ajouter une observation de vie scolaire avec pièces jointes."""
    from eleves.utils_annee import get_annee_active

    ecole = user_school(request.user)
    annee_active = get_annee_active(request, ecole) if ecole else None

    if request.method == 'POST':
        form = ActiviteJournaliereForm(request.POST)
        pj_form = PieceJointeActiviteForm(request.POST, request.FILES)

        if form.is_valid() and pj_form.is_valid():
            activite = form.save(commit=False)
            activite.cree_par = request.user
            activite.save()

            # Pièces jointes multiples
            for f in request.FILES.getlist('fichiers'):
                PieceJointeActivite.objects.create(
                    activite=activite,
                    fichier=f,
                    legende=f.name,
                )

            messages.success(request, f"Observation « {activite.titre} » ajoutée avec succès.")
            return redirect('notes:liste_activites')
    else:
        form = ActiviteJournaliereForm(initial={'date': date.today()})
        pj_form = PieceJointeActiviteForm()

    # Limiter les classes à l'école de l'utilisateur
    classes_qs = ClasseNote.objects.filter(actif=True).order_by('niveau', 'nom')
    if ecole:
        classes_qs = classes_qs.filter(ecole=ecole)
    if annee_active:
        classes_qs = classes_qs.filter(annee_scolaire=annee_active)
    form.fields['classe'].queryset = classes_qs
    # Élèves seront chargés en AJAX
    form.fields['eleve'].queryset = Eleve.objects.none()

    # Si la classe a déjà été choisie (validation échouée)
    if request.POST.get('classe'):
        try:
            classe_note = ClasseNote.objects.get(pk=request.POST['classe'])
            eleves = Eleve.objects.filter(
                classe__nom=classe_note.nom,
                classe__ecole=classe_note.ecole,
                statut='ACTIF'
            ).order_by('nom', 'prenom')
            form.fields['eleve'].queryset = eleves
        except (ClasseNote.DoesNotExist, ValueError):
            pass

    context = {
        'form': form,
        'pj_form': pj_form,
        'mode': 'ajouter',
    }
    return render(request, 'notes/activites/form.html', context)


@login_required
def modifier_activite(request, activite_id):
    """Modifier une observation existante."""
    activite = get_object_or_404(ActiviteJournaliere, pk=activite_id)

    if request.method == 'POST':
        form = ActiviteJournaliereForm(request.POST, instance=activite)
        pj_form = PieceJointeActiviteForm(request.POST, request.FILES)

        if form.is_valid() and pj_form.is_valid():
            form.save()

            for f in request.FILES.getlist('fichiers'):
                PieceJointeActivite.objects.create(
                    activite=activite,
                    fichier=f,
                    legende=f.name,
                )

            messages.success(request, "Observation modifiée avec succès.")
            return redirect('notes:detail_activite', activite_id=activite.pk)
    else:
        form = ActiviteJournaliereForm(instance=activite)
        pj_form = PieceJointeActiviteForm()

    # Charger les classes et élèves correspondants
    ecole = user_school(request.user)
    classes_qs = ClasseNote.objects.filter(actif=True).order_by('niveau', 'nom')
    if ecole:
        classes_qs = classes_qs.filter(ecole=ecole)
    form.fields['classe'].queryset = classes_qs

    eleves = Eleve.objects.filter(
        classe__nom=activite.classe.nom,
        classe__ecole=activite.classe.ecole,
        statut='ACTIF'
    ).order_by('nom', 'prenom')
    form.fields['eleve'].queryset = eleves

    context = {
        'form': form,
        'pj_form': pj_form,
        'activite': activite,
        'mode': 'modifier',
    }
    return render(request, 'notes/activites/form.html', context)


@login_required
def detail_activite(request, activite_id):
    """Détail d'une observation avec ses pièces jointes."""
    activite = get_object_or_404(
        ActiviteJournaliere.objects.select_related('eleve', 'classe', 'cree_par').prefetch_related('pieces_jointes'),
        pk=activite_id
    )
    context = {'activite': activite}
    return render(request, 'notes/activites/detail.html', context)


@login_required
def supprimer_activite(request, activite_id):
    """Supprimer une observation."""
    activite = get_object_or_404(ActiviteJournaliere, pk=activite_id)
    if request.method == 'POST':
        activite.delete()
        messages.success(request, "Observation supprimée.")
        return redirect('notes:liste_activites')
    return render(request, 'notes/activites/confirmer_suppression.html', {'activite': activite})


@login_required
def supprimer_piece_jointe(request, pj_id):
    """Supprimer une pièce jointe (AJAX)."""
    pj = get_object_or_404(PieceJointeActivite, pk=pj_id)
    activite_id = pj.activite_id
    if request.method == 'POST':
        pj.fichier.delete(save=False)
        pj.delete()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        messages.success(request, "Pièce jointe supprimée.")
        return redirect('notes:detail_activite', activite_id=activite_id)
    return JsonResponse({'error': 'POST requis'}, status=405)


@login_required
def api_eleves_par_classe_note(request):
    """API AJAX : retourne les élèves d'une ClasseNote."""
    classe_id = request.GET.get('classe_id')
    if not classe_id:
        return JsonResponse([], safe=False)
    try:
        classe_note = ClasseNote.objects.get(pk=classe_id)
        eleves = Eleve.objects.filter(
            classe__nom=classe_note.nom,
            classe__ecole=classe_note.ecole,
            statut='ACTIF'
        ).order_by('nom', 'prenom').values('id', 'nom', 'prenom', 'matricule')
        return JsonResponse(list(eleves), safe=False)
    except ClasseNote.DoesNotExist:
        return JsonResponse([], safe=False)
