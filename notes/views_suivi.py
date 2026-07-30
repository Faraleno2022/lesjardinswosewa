"""
Saisie des notes de suivi continu (cours/interrogations, orales, écrites,
devoirs, participation) qui produisent un bonus plafonné sur la note mensuelle.
"""
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from eleves.models import Classe as ClasseEleve, Eleve
from .models import ClasseNote, MatiereNote, NoteSuivi
from .calculs_moyennes import bonus_suivi_batch
from .utils_rangs import invalider_cache_rangs


def _eleves_de_classe_note(classe_note):
    """Élèves actifs correspondant à une ClasseNote (mapping par nom+année+école)."""
    classe_eleve = ClasseEleve.objects.filter(
        nom=classe_note.nom,
        annee_scolaire=classe_note.annee_scolaire,
        ecole=classe_note.ecole,
    ).first()
    if not classe_eleve:
        return []
    return list(Eleve.objects.filter(classe=classe_eleve, statut='ACTIF')
                .order_by('prenom', 'nom'))


@login_required
def toggle_bonus_suivi(request):
    """Active/désactive le bonus de suivi pour l'école de l'utilisateur."""
    profil = getattr(request.user, 'profil', None)
    ecole = profil.ecole if profil else None
    retour = request.POST.get('next') or request.GET.get('next') or 'notes:saisie_suivi'
    if not ecole:
        messages.error(request, "Aucune école associée à votre compte.")
        return redirect('notes:saisie_suivi')
    if request.method == 'POST':
        ecole.bonus_suivi_actif = not ecole.bonus_suivi_actif
        ecole.save(update_fields=['bonus_suivi_actif'])
        # Recalcul nécessaire: vider le cache des moyennes/rangs
        from .utils_rangs import invalider_cache_rangs
        for cn in ClasseNote.objects.filter(ecole=ecole, actif=True):
            invalider_cache_rangs(cn)
        if ecole.bonus_suivi_actif:
            messages.success(request, "✅ Bonus de suivi ACTIVÉ pour votre école.")
        else:
            messages.info(request, "⛔ Bonus de suivi DÉSACTIVÉ pour votre école.")
    try:
        return redirect(retour)
    except Exception:
        return redirect('notes:saisie_suivi')


@login_required
def saisie_suivi(request):
    """Saisie d'une colonne de notes de suivi (classe + matière + mois + type)."""
    user_profil = getattr(request.user, 'profil', None)
    ecole = user_profil.ecole if user_profil else None
    if ecole:
        classes = ClasseNote.objects.filter(ecole=ecole, actif=True).order_by('niveau', 'nom')
    else:
        classes = ClasseNote.objects.filter(actif=True).order_by('niveau', 'nom')

    classe_id = (request.GET.get('classe_id') or request.POST.get('classe_id') or '').strip()
    matiere_id = (request.GET.get('matiere_id') or request.POST.get('matiere_id') or '').strip()
    mois = (request.GET.get('mois') or request.POST.get('mois') or '').strip()
    type_note = (request.GET.get('type_note') or request.POST.get('type_note') or 'COURS').strip()
    numero_raw = (request.GET.get('numero') or request.POST.get('numero') or '1').strip()
    try:
        numero = max(1, min(20, int(numero_raw)))
    except (ValueError, TypeError):
        numero = 1

    classe = None
    matiere = None
    matieres = []
    eleves = []
    notes_existantes = {}

    if classe_id.isdigit():
        classe = get_object_or_404(ClasseNote, pk=int(classe_id))
        matieres = list(MatiereNote.objects.filter(classe=classe, actif=True).order_by('nom'))
        eleves = _eleves_de_classe_note(classe)
        if matiere_id.isdigit():
            matiere = next((m for m in matieres if m.id == int(matiere_id)), None)

    if request.method == 'POST' and classe and matiere and mois and type_note:
        enregistres, supprimes = 0, 0
        annee = classe.annee_scolaire
        for eleve in eleves:
            brut = (request.POST.get(f'note_{eleve.id}') or '').strip().replace(',', '.')
            if brut == '':
                # champ vide -> supprimer la note existante de ce type/mois/numero
                supprimes += NoteSuivi.objects.filter(
                    eleve=eleve, matiere=matiere, mois=mois,
                    type_note=type_note, numero=numero, annee_scolaire=annee).delete()[0]
                continue
            try:
                valeur = Decimal(brut)
            except (InvalidOperation, ValueError):
                continue
            if valeur < 0 or valeur > 20:
                continue
            NoteSuivi.objects.update_or_create(
                eleve=eleve, matiere=matiere, mois=mois,
                type_note=type_note, numero=numero, annee_scolaire=annee,
                defaults={'note': valeur, 'cree_par': request.user},
            )
            enregistres += 1
        # Invalider les moyennes/rangs (le bonus modifie la note du mois)
        invalider_cache_rangs(classe, mois)
        messages.success(
            request,
            f"Suivi enregistré : {enregistres} note(s), {supprimes} supprimée(s) — "
            f"{matiere.nom} / {mois} / {dict(NoteSuivi.TYPE_CHOICES).get(type_note, type_note)}.")
        return redirect(f"{request.path}?classe_id={classe.id}&matiere_id={matiere.id}"
                        f"&mois={mois}&type_note={type_note}&numero={numero}")

    # Pré-remplissage : notes existantes de ce type + aperçu du bonus global
    apercu_bonus = {}
    if classe and matiere and mois:
        for ns in NoteSuivi.objects.filter(matiere=matiere, mois=mois, type_note=type_note,
                                           numero=numero, annee_scolaire=classe.annee_scolaire):
            notes_existantes[ns.eleve_id] = ns.note
        # Bonus courant (toutes composantes confondues) pour ce mois
        bmap = bonus_suivi_batch([e.id for e in eleves], [matiere.id], [mois], classe.annee_scolaire)
        for e in eleves:
            apercu_bonus[e.id] = round(bmap.get((e.id, matiere.id, mois), 0.0), 2)

    lignes = [{
        'eleve': e,
        'note': notes_existantes.get(e.id, ''),
        'bonus': apercu_bonus.get(e.id, 0.0),
    } for e in eleves]

    context = {
        'titre_page': "Notes de suivi (bonus)",
        'classes': classes,
        'classe': classe,
        'classe_id': classe_id,
        'matieres': matieres,
        'matiere': matiere,
        'matiere_id': matiere_id,
        'mois': mois,
        'mois_choices': NoteSuivi.MOIS_CHOICES,
        'type_note': type_note,
        'type_choices': NoteSuivi.TYPE_CHOICES,
        'numero': numero,
        'numeros': range(1, 11),
        'lignes': lignes,
        'bonus_max': 2,
        'bonus_actif': bool(getattr(ecole, 'bonus_suivi_actif', False)),
    }
    return render(request, 'notes/saisie_suivi.html', context)
