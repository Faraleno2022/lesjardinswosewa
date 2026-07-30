"""
Module pour le Tableau d'Honneur de l'établissement
Affiche les premiers de chaque classe, classés entre eux
"""
import base64
import os
import logging
from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import HttpResponse
from django.template.loader import render_to_string

from .models import ClasseNote, MatiereNote
from eleves.models import Eleve, Classe as ClasseEleve
from utilisateurs.utils import filter_by_user_school, user_school
from eleves.utils_annee import get_annee_active
from .calculs_moyennes import calculer_classement_classe, detecter_niveau_scolaire
from .export_classement import formater_rang

logger = logging.getLogger(__name__)


PERIODES_CHOICES = [
    ('OCTOBRE', 'Octobre'),
    ('NOVEMBRE', 'Novembre'),
    ('DECEMBRE', 'Décembre'),
    ('JANVIER', 'Janvier'),
    ('FEVRIER', 'Février'),
    ('MARS', 'Mars'),
    ('AVRIL', 'Avril'),
    ('MAI', 'Mai'),
    ('JUIN', 'Juin'),
    ('TRIMESTRE_1', '1er Trimestre'),
    ('TRIMESTRE_2', '2ème Trimestre'),
    ('TRIMESTRE_3', '3ème Trimestre'),
    ('SEMESTRE_1', '1er Semestre'),
    ('SEMESTRE_2', '2ème Semestre'),
    ('ANNUEL_TRIM', 'Annuel (Trimestres)'),
    ('ANNUEL_SEM', 'Annuel (Semestres)'),
]


def _get_system_type(periode):
    """Détermine le type de système selon la période"""
    if periode in ['TRIMESTRE_1', 'TRIMESTRE_2', 'TRIMESTRE_3']:
        return 'trimestriel'
    elif periode in ['SEMESTRE_1', 'SEMESTRE_2']:
        return 'semestriel'
    elif periode == 'ANNUEL_TRIM':
        return 'annuel_trimestriel'
    elif periode == 'ANNUEL_SEM':
        return 'annuel_semestriel'
    return 'mensuel'


def _get_periode_label(periode):
    """Retourne le libellé lisible de la période"""
    for code, label in PERIODES_CHOICES:
        if code == periode:
            return label
    return periode


def _get_top1_par_classe(request, periode):
    """
    Récupère le premier élève de chaque classe pour une période donnée.
    Retourne une liste triée par moyenne décroissante (premier des premiers en tête).
    """
    ecole = user_school(request.user)
    annee_active = get_annee_active(request, ecole) if ecole else None
    qs = ClasseNote.objects.filter(actif=True)
    if annee_active:
        qs = qs.filter(annee_scolaire=annee_active)
    classes_note = filter_by_user_school(
        qs.order_by('niveau', 'nom'),
        request.user, 'ecole'
    )

    system_type = _get_system_type(periode)
    premiers = []

    for classe_note in classes_note:
        try:
            niveau = detecter_niveau_scolaire(classe_note.nom)
            est_maternelle = (niveau == 'MATERNELLE')
            est_primaire = (niveau == 'PRIMAIRE')
            note_max = 10 if est_primaire else 20

            # Récupérer la classe élève correspondante
            classe_eleve = ClasseEleve.objects.filter(
                nom__iexact=classe_note.nom,
                annee_scolaire=classe_note.annee_scolaire,
                ecole=classe_note.ecole
            ).first()
            if not classe_eleve:
                continue

            eleves = Eleve.objects.filter(classe=classe_eleve, statut='ACTIF')
            if not eleves.exists():
                continue

            total_eleves = eleves.count()

            if est_maternelle:
                # Utiliser le calcul des rangs maternelle
                from .utils_rangs import calculer_rangs_classe_periode
                rangs_dict = calculer_rangs_classe_periode(classe_note, periode, use_cache=False)
                if not rangs_dict:
                    continue

                # Trouver le premier (rang_num == 1)
                for eleve in eleves:
                    rang_info = rangs_dict.get(eleve.id)
                    if rang_info and rang_info.get('rang_num') == 1:
                        photo_base64, photo_mime = _encode_photo(eleve)
                        premiers.append({
                            'eleve': eleve,
                            'classe_nom': classe_note.nom,
                            'moyenne': float(rang_info['moyenne']),
                            'rang_classe': 1,
                            'total_eleves': total_eleves,
                            'note_max': 100,  # Taux d'acquisition en %
                            'est_maternelle': True,
                            'est_primaire': False,
                            'niveau': 'MATERNELLE',
                            'photo_base64': photo_base64,
                            'photo_mime': photo_mime or 'image/jpeg',
                            'rang_formate': formater_rang(1, getattr(eleve, 'sexe', 'M')),
                        })
                        break
            else:
                # Calcul standard
                matieres = MatiereNote.objects.filter(classe=classe_note, actif=True)
                if not matieres.exists():
                    continue

                classement_resultat = calculer_classement_classe(
                    eleves, matieres, periode, system_type, use_cache=False
                )
                if not classement_resultat or not classement_resultat.get('classement'):
                    continue

                # Le premier du classement
                eleve_id, moyenne = classement_resultat['classement'][0]
                if moyenne <= 0:
                    continue

                try:
                    eleve = Eleve.objects.get(pk=eleve_id)
                except Eleve.DoesNotExist:
                    continue

                photo_base64, photo_mime = _encode_photo(eleve)
                premiers.append({
                    'eleve': eleve,
                    'classe_nom': classe_note.nom,
                    'moyenne': round(float(moyenne), 2),
                    'rang_classe': 1,
                    'total_eleves': total_eleves,
                    'note_max': note_max,
                    'est_maternelle': False,
                    'est_primaire': est_primaire,
                    'niveau': 'PRIMAIRE' if est_primaire else 'SECONDAIRE',
                    'photo_base64': photo_base64,
                    'photo_mime': photo_mime or 'image/jpeg',
                    'rang_formate': formater_rang(1, getattr(eleve, 'sexe', 'M')),
                })

        except Exception as e:
            logger.error(f"Erreur tableau d'honneur pour {classe_note.nom}: {e}")
            continue

    # Trier par moyenne normalisée décroissante (pour comparer /10 et /20 et %)
    def moyenne_normalisee(item):
        if item['est_maternelle']:
            return item['moyenne']  # déjà en %
        elif item['est_primaire']:
            return (item['moyenne'] / 10) * 100
        else:
            return (item['moyenne'] / 20) * 100

    premiers.sort(key=lambda x: -moyenne_normalisee(x))

    # Attribuer le rang parmi les premiers
    for idx, premier in enumerate(premiers, start=1):
        premier['rang_premiers'] = idx
        sexe = getattr(premier['eleve'], 'sexe', 'M') or 'M'
        premier['rang_premiers_formate'] = formater_rang(idx, sexe)

    return premiers


def _encode_photo(eleve):
    """Encode la photo d'un élève en base64, retourne (base64_str, mime_type) ou (None, None)"""
    if eleve.photo:
        try:
            photo_path = eleve.photo.path
            if os.path.exists(photo_path):
                ext = os.path.splitext(photo_path)[1].lower()
                mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                            '.png': 'image/png', '.gif': 'image/gif',
                            '.webp': 'image/webp'}
                mime = mime_map.get(ext, 'image/jpeg')
                with open(photo_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8'), mime
        except Exception:
            pass
    return None, None


NIVEAUX_CHOICES = [
    ('ETABLISSEMENT', 'Établissement (Primaire + Secondaire)'),
    ('PRIMAIRE', 'Primaire'),
    ('SECONDAIRE', 'Secondaire'),
    ('MATERNELLE', 'Maternelle'),
]


def _identifier_premier_global(premiers):
    """Identifie le premier global dans une liste de premiers et retourne son index."""
    if not premiers:
        return -1
    # Le premier de la liste triée est le meilleur
    return 0


@login_required
def tableau_honneur(request):
    """Vue HTML du tableau d'honneur avec classements par niveau"""
    periode = request.GET.get('periode', '')
    niveau_filtre = request.GET.get('niveau', 'ETABLISSEMENT')

    # Récupérer l'école
    from utilisateurs.utils import user_school
    ecole = user_school(request.user)

    context = {
        'periodes': PERIODES_CHOICES,
        'niveaux': NIVEAUX_CHOICES,
        'periode': periode,
        'niveau_filtre': niveau_filtre,
        'periode_label': _get_periode_label(periode) if periode else '',
        'ecole': ecole,
        'premiers': [],
        'premier_global': None,
    }

    if periode:
        tous_premiers = _get_top1_par_classe(request, periode)

        if niveau_filtre == 'ETABLISSEMENT':
            # Exclure la maternelle → Primaire + Secondaire ensemble
            premiers = [p for p in tous_premiers if p.get('niveau') in ('PRIMAIRE', 'SECONDAIRE')]
        elif niveau_filtre:
            premiers = [p for p in tous_premiers if p.get('niveau') == niveau_filtre]
        else:
            premiers = tous_premiers

        # Re-numéroter les rangs après le filtrage
        for idx, premier in enumerate(premiers, start=1):
            premier['rang_premiers'] = idx
            sexe = getattr(premier['eleve'], 'sexe', 'M') or 'M'
            premier['rang_premiers_formate'] = formater_rang(idx, sexe)

        context['premiers'] = premiers
        if premiers:
            context['premier_global'] = premiers[0]

    return render(request, 'notes/tableau_honneur.html', context)


@login_required
def tableau_honneur_pdf(request):
    """Export PDF du tableau d'honneur"""
    periode = request.GET.get('periode', '')
    niveau_filtre = request.GET.get('niveau', 'ETABLISSEMENT')

    if not periode:
        return HttpResponse("Période non spécifiée", status=400)

    from utilisateurs.utils import user_school
    ecole = user_school(request.user)

    tous_premiers = _get_top1_par_classe(request, periode)
    if niveau_filtre == 'ETABLISSEMENT':
        premiers = [p for p in tous_premiers if p.get('niveau') in ('PRIMAIRE', 'SECONDAIRE')]
    elif niveau_filtre:
        premiers = [p for p in tous_premiers if p.get('niveau') == niveau_filtre]
    else:
        premiers = tous_premiers

    # Re-numéroter les rangs
    for idx, premier in enumerate(premiers, start=1):
        premier['rang_premiers'] = idx
        sexe = getattr(premier['eleve'], 'sexe', 'M') or 'M'
        premier['rang_premiers_formate'] = formater_rang(idx, sexe)

    if not premiers:
        return HttpResponse("Aucun premier trouvé pour cette période", status=404)

    # Logo école en base64
    logo_base64 = None
    if ecole and ecole.logo:
        try:
            logo_path = ecole.logo.path
            if os.path.exists(logo_path):
                with open(logo_path, 'rb') as f:
                    logo_base64 = base64.b64encode(f.read()).decode('utf-8')
        except Exception:
            pass

    annee_scolaire = get_annee_active(request, ecole) or ''

    niveau_labels_map = {
        'ETABLISSEMENT': 'Établissement (Primaire + Secondaire)',
        'MATERNELLE': 'Maternelle',
        'PRIMAIRE': 'Primaire',
        'SECONDAIRE': 'Secondaire',
    }
    niveau_label = niveau_labels_map.get(niveau_filtre, 'Tous les niveaux')

    context = {
        'premiers': premiers,
        'premier_global': premiers[0] if premiers else None,
        'periode': periode,
        'periode_label': _get_periode_label(periode),
        'niveau_filtre': niveau_filtre,
        'niveau_label': niveau_label,
        'ecole': ecole,
        'logo_base64': logo_base64,
        'annee_scolaire': annee_scolaire,
        'date_emission': datetime.now().strftime('%d/%m/%Y'),
    }

    html_content = render_to_string('notes/tableau_honneur_pdf.html', context, request=request)

    # Import lazy pour eviter l'erreur GTK au demarrage de l'application
    from weasyprint import HTML, CSS
    html = HTML(string=html_content)
    css = CSS(string='''
        @page {
            size: A4 landscape;
            margin: 10mm;
        }
    ''')

    pdf = html.write_pdf(stylesheets=[css])

    response = HttpResponse(pdf, content_type='application/pdf')
    suffix = f"_{niveau_filtre.lower()}" if niveau_filtre else ""
    response['Content-Disposition'] = (
        f'inline; filename="tableau_honneur_{periode}{suffix}.pdf"'
    )
    return response
