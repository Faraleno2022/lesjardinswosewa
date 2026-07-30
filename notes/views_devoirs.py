"""
Suivi des devoirs : liste des devoirs donnés par classe + qui a rendu.
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render, redirect, get_object_or_404

from eleves.models import Classe as ClasseEleve, Eleve
from .models import ClasseNote, MatiereNote, Devoir, RemiseDevoir
from .calculs_moyennes import mois_scolaire_depuis_date
from .utils_rangs import invalider_cache_rangs


def _eleves_de_classe_note(classe_note):
    ce = ClasseEleve.objects.filter(
        nom=classe_note.nom, annee_scolaire=classe_note.annee_scolaire, ecole=classe_note.ecole
    ).first()
    if not ce:
        return []
    return list(Eleve.objects.filter(classe=ce, statut='ACTIF').order_by('prenom', 'nom'))


def _classes_utilisateur(request):
    profil = getattr(request.user, 'profil', None)
    ecole = profil.ecole if profil else None
    qs = ClasseNote.objects.filter(actif=True)
    if ecole:
        qs = qs.filter(ecole=ecole)
    return qs.order_by('niveau', 'nom')


@login_required
def liste_devoirs(request):
    """Liste des devoirs (filtrable par classe), avec compteurs de rendus."""
    classes = list(_classes_utilisateur(request))
    classe_id = (request.GET.get('classe_id') or '').strip()

    devoirs = (Devoir.objects
               .select_related('classe', 'matiere')
               .annotate(
                   nb_rendus=Count('remises', filter=Q(remises__statut__in=['RENDU', 'EN_RETARD'])),
                   nb_non_rendus=Count('remises', filter=Q(remises__statut='NON_RENDU')),
                   nb_total=Count('remises'),
               )
               .order_by('-date_remise'))
    classe = None
    if classe_id.isdigit():
        classe = next((c for c in classes if c.id == int(classe_id)), None)
        devoirs = devoirs.filter(classe_id=int(classe_id))
    else:
        devoirs = devoirs.filter(classe__in=classes)

    return render(request, 'notes/devoirs_liste.html', {
        'titre_page': "Suivi des devoirs",
        'classes': classes,
        'classe': classe,
        'classe_id': classe_id,
        'devoirs': list(devoirs),
        'today': date.today(),
    })


@login_required
def creer_devoir(request):
    """Créer un nouveau devoir."""
    classes = list(_classes_utilisateur(request))
    classe_id = (request.GET.get('classe_id') or request.POST.get('classe_id') or '').strip()
    classe = None
    matieres = []
    if classe_id.isdigit():
        classe = next((c for c in classes if c.id == int(classe_id)), None)
        if classe:
            matieres = list(MatiereNote.objects.filter(classe=classe, actif=True).order_by('nom'))

    if request.method == 'POST' and classe:
        matiere_id = (request.POST.get('matiere_id') or '').strip()
        titre = (request.POST.get('titre') or '').strip()
        description = (request.POST.get('description') or '').strip()
        date_donne = request.POST.get('date_donne') or date.today().isoformat()
        date_remise = request.POST.get('date_remise') or date.today().isoformat()
        compte_bonus = request.POST.get('compte_bonus') == '1'
        matiere = next((m for m in matieres if str(m.id) == matiere_id), None)
        if not (matiere and titre):
            messages.error(request, "Matière et titre sont obligatoires.")
        else:
            devoir = Devoir.objects.create(
                classe=classe, matiere=matiere, titre=titre, description=description,
                date_donne=date_donne, date_remise=date_remise,
                compte_bonus=compte_bonus, cree_par=request.user)
            # Créer les remises (statut NON_RENDU) pour tous les élèves actifs
            eleves = _eleves_de_classe_note(classe)
            RemiseDevoir.objects.bulk_create([
                RemiseDevoir(devoir=devoir, eleve=e, statut='NON_RENDU') for e in eleves
            ])
            messages.success(request, f"Devoir « {titre} » créé pour {len(eleves)} élève(s).")
            return redirect('notes:suivi_devoir', devoir_id=devoir.id)

    return render(request, 'notes/devoir_form.html', {
        'titre_page': "Nouveau devoir",
        'classes': classes,
        'classe': classe,
        'classe_id': classe_id,
        'matieres': matieres,
        'today': date.today(),
    })


@login_required
def suivi_devoir(request, devoir_id):
    """Marquer le statut de remise de chaque élève pour un devoir."""
    devoir = get_object_or_404(
        Devoir.objects.select_related('classe', 'matiere'), pk=devoir_id)
    eleves = _eleves_de_classe_note(devoir.classe)

    remises = {r.eleve_id: r for r in RemiseDevoir.objects.filter(devoir=devoir)}
    # Créer les remises manquantes (élèves ajoutés après)
    manquants = [RemiseDevoir(devoir=devoir, eleve=e, statut='NON_RENDU')
                 for e in eleves if e.id not in remises]
    if manquants:
        RemiseDevoir.objects.bulk_create(manquants)
        remises = {r.eleve_id: r for r in RemiseDevoir.objects.filter(devoir=devoir)}

    if request.method == 'POST':
        # Activation/désactivation du bonus depuis la page de suivi
        nouveau_compte_bonus = request.POST.get('compte_bonus') == '1'
        if nouveau_compte_bonus != devoir.compte_bonus:
            devoir.compte_bonus = nouveau_compte_bonus
            devoir.save(update_fields=['compte_bonus'])
        maj = 0
        statuts_valides = dict(RemiseDevoir.STATUT_CHOICES)
        for eleve in eleves:
            r = remises.get(eleve.id)
            if not r:
                continue
            statut = (request.POST.get(f'statut_{eleve.id}') or 'NON_RENDU').strip()
            if statut not in statuts_valides:
                statut = 'NON_RENDU'
            note_brut = (request.POST.get(f'note_{eleve.id}') or '').strip().replace(',', '.')
            note_val = None
            if note_brut:
                try:
                    v = float(note_brut)
                    if 0 <= v <= 20:
                        note_val = v
                except ValueError:
                    note_val = None
            r.statut = statut
            r.note = note_val
            r.save(update_fields=['statut', 'note', 'date_modification'])
            maj += 1
        # Si le devoir compte dans le bonus, invalider les moyennes/rangs du mois
        if devoir.compte_bonus:
            mois = mois_scolaire_depuis_date(devoir.date_remise)
            if mois:
                invalider_cache_rangs(devoir.classe, mois)
        messages.success(request, f"Suivi mis à jour pour {maj} élève(s).")
        return redirect('notes:suivi_devoir', devoir_id=devoir.id)

    lignes = [{'eleve': e, 'remise': remises.get(e.id)} for e in eleves]
    return render(request, 'notes/devoir_suivi.html', {
        'titre_page': f"Suivi : {devoir.titre}",
        'devoir': devoir,
        'lignes': lignes,
        'statut_choices': RemiseDevoir.STATUT_CHOICES,
    })


@login_required
def supprimer_devoir(request, devoir_id):
    devoir = get_object_or_404(Devoir, pk=devoir_id)
    if request.method == 'POST':
        classe_id = devoir.classe_id
        titre = devoir.titre
        devoir.delete()
        messages.success(request, f"Devoir « {titre} » supprimé.")
        return redirect(f"{redirect('notes:liste_devoirs').url}?classe_id={classe_id}")
    return redirect('notes:liste_devoirs')
