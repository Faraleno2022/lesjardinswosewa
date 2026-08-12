from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden
from datetime import datetime
from decimal import Decimal

from eleves.models import Classe
from eleves.utils_annee import get_annee_active
from paiements.models import Paiement
from paiements.calculs import filtre_types_scolarite, normaliser_libelle
from utilisateurs.utils import user_is_admin, user_school
from rapports.utils import _draw_header_and_watermark

# ReportLab
# ReportLab: fera l'objet d'un import différé dans la vue PDF


TRANCHES_EXPORT_HEADERS = [
    'Élève',
    'Inscription payée',
    'Réinscription payée',
    'Tranche 1 payée',
    'Tranche 2 payée',
    'Tranche 3 payée',
    'Total dû',
    'Total payé',
    'Reste',
]


def _paiements_fallback_par_poste(eleve, annee_scolaire=None):
    """Totalise les reçus sans compter plusieurs fois un paiement combiné.

    Sans échéancier la ventilation d'un reçu combiné est indémontrable : son
    montant est conservé dans le total, mais pas inventé dans plusieurs
    colonnes de tranches.
    """
    paiements = Paiement.objects.filter(eleve=eleve, statut='VALIDE').filter(
        filtre_types_scolarite()
    )
    if annee_scolaire:
        paiements = paiements.filter(annee_scolaire=annee_scolaire)
    postes = {
        'inscription': Decimal('0'),
        'reinscription': Decimal('0'),
        'tranche_1': Decimal('0'),
        'tranche_2': Decimal('0'),
        'tranche_3': Decimal('0'),
    }
    total = Decimal('0')
    for paiement in paiements.select_related('type_paiement'):
        montant = Decimal(str(paiement.montant or 0))
        total += montant
        nom = normaliser_libelle(paiement.type_paiement.nom)
        cibles = []
        compact = ''.join(nom.split())
        if 'reinscription' in compact:
            cibles.append('reinscription')
        elif 'inscription' in nom:
            cibles.append('inscription')
        for numero in (1, 2, 3):
            if f'tranche {numero}' in nom or f'tranche{numero}' in nom:
                cibles.append(f'tranche_{numero}')
        if len(cibles) == 1:
            postes[cibles[0]] += montant
    return postes, total


def _donnees_tranches_eleve(eleve, annee_scolaire=None):
    """Retourne une ligne commune aux exports PDF et Excel.

    Les frais d'admission sont placés dans une seule des deux colonnes selon
    ``nature_frais``. Ils ne sont donc jamais comptés deux fois dans le total.
    """
    if annee_scolaire:
        echeancier = eleve.echeanciers.filter(
            annee_scolaire=annee_scolaire
        ).first()
    else:
        echeancier = getattr(eleve, 'echeancier', None)

    inscription = reinscription = Decimal('0')
    tranche_1 = tranche_2 = tranche_3 = Decimal('0')
    total_du = total_paye = reste = Decimal('0')

    if echeancier is not None:
        admission_payee = Decimal(str(echeancier.frais_inscription_paye or 0))
        if echeancier.nature_frais == 'REINSCRIPTION':
            reinscription = admission_payee
        else:
            inscription = admission_payee
        tranche_1 = Decimal(str(echeancier.tranche_1_payee or 0))
        tranche_2 = Decimal(str(echeancier.tranche_2_payee or 0))
        tranche_3 = Decimal(str(echeancier.tranche_3_payee or 0))
        total_du = Decimal(str(echeancier.total_du or 0))
        total_paye = inscription + reinscription + tranche_1 + tranche_2 + tranche_3
        reste = max(Decimal('0'), total_du - total_paye)
    else:
        postes, total_paye = _paiements_fallback_par_poste(eleve, annee_scolaire)
        inscription = postes['inscription']
        reinscription = postes['reinscription']
        tranche_1 = postes['tranche_1']
        tranche_2 = postes['tranche_2']
        tranche_3 = postes['tranche_3']

    return {
        'inscription': inscription,
        'reinscription': reinscription,
        'tranche_1': tranche_1,
        'tranche_2': tranche_2,
        'tranche_3': tranche_3,
        'total_du': total_du,
        'total_paye': Decimal(str(total_paye or 0)),
        'reste': reste,
    }


@login_required
def export_tranches_par_classe_pdf(request):
    """Export PDF des tranches par classe avec logo entête et filigrane.

    Filtres GET:
    - ecole: id de l'école
    - classe: id de la classe
    - annee_scolaire: ex '2024-2025'

    Respecte la séparation par école pour les non-admins.
    """
    # Contrôle d'accès: Admin ou Comptable uniquement
    is_admin = user_is_admin(request.user)
    is_comptable = False
    try:
        if hasattr(request.user, 'profil'):
            is_comptable = (getattr(request.user.profil, 'role', None) == 'COMPTABLE')
    except Exception:
        is_comptable = False
    if not (is_admin or is_comptable):
        return HttpResponseForbidden("Accès refusé: vous n'avez pas l'autorisation d'exporter ce rapport.")

    # Lecture et validation des paramètres
    raw_ecole = (request.GET.get('ecole') or '').strip()
    raw_classe = (request.GET.get('classe') or request.GET.get('classe_id') or '').strip()
    annee_scolaire = (request.GET.get('annee_scolaire') or '').strip()

    def parse_int(value):
        try:
            return int(value)
        except Exception:
            return None

    ecole_id = parse_int(raw_ecole) if raw_ecole else None
    classe_id = parse_int(raw_classe) if raw_classe else None

    # Scope classes (filtrées par année active)
    classes = Classe.objects.select_related('ecole').all()
    ecole_user = user_school(request.user)
    annee_active = get_annee_active(request, ecole_user) if ecole_user else None
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    if restreindre:
        classes = classes.filter(ecole=ecole_user)
    elif ecole_id:
        classes = classes.filter(ecole_id=ecole_id)
    if classe_id:
        classes = classes.filter(id=classe_id)
    if annee_active and not annee_scolaire:
        classes = classes.filter(annee_scolaire=annee_active)
    elif annee_scolaire:
        classes = classes.filter(annee_scolaire=annee_scolaire)

    # Anti-abus: limiter le nombre de classes exportées en une requête
    classes = classes.order_by('ecole__nom', 'niveau', 'nom')[:200]

    # Préparer réponse PDF
    response = HttpResponse(content_type='application/pdf')
    suffix = datetime.now().strftime('%Y%m%d')
    response['Content-Disposition'] = f'attachment; filename="tranches_par_classe_{suffix}.pdf"'

    # Import différé de ReportLab pour éviter les erreurs si non installé
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
    except Exception:
        return HttpResponse("ReportLab n'est pas installé. Veuillez exécuter: pip install reportlab", status=500)

    doc = SimpleDocTemplate(
        response,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=60, bottomMargin=30
    )
    elements = []
    styles = getSampleStyleSheet()
    cell = ParagraphStyle('Cell', parent=styles['Normal'], fontSize=8, leading=9)

    titre = 'Tranches par classe'
    if annee_scolaire:
        titre += f" – Année {annee_scolaire}"
    elements.append(Paragraph(titre, styles['Title']))
    elements.append(Spacer(1, 0.5*cm))

    header = TRANCHES_EXPORT_HEADERS

    def P(x):
        return Paragraph(str(x or ''), cell)

    # Parcours des classes
    for classe in classes:
        # Titre de la classe
        titre_classe = f"Classe: {classe.nom} – {getattr(classe.ecole, 'nom', '')}"
        elements.append(Paragraph(titre_classe, styles['Heading2']))
        elements.append(Spacer(1, 0.2*cm))

        data = [header]

        # Élèves de la classe
        # Utiliser le related_name défini sur Eleve.classe = 'eleves'
        eleves = getattr(classe, 'eleves', None)
        if eleves is not None:
            eleves = eleves.all().order_by('nom', 'prenom')
        else:
            eleves = []

        for e in eleves:
            ligne = _donnees_tranches_eleve(e, annee_scolaire)

            # Construire le nom de l'élève sans déclencher d'erreur si un attribut manque
            nom_affiche = getattr(e, 'nom_complet', None) or f"{getattr(e, 'prenom', '')} {getattr(e, 'nom', '')}".strip()
            data.append([
                P(nom_affiche),
                f"{ligne['inscription']:,}".replace(',', ' '),
                f"{ligne['reinscription']:,}".replace(',', ' '),
                f"{ligne['tranche_1']:,}".replace(',', ' '),
                f"{ligne['tranche_2']:,}".replace(',', ' '),
                f"{ligne['tranche_3']:,}".replace(',', ' '),
                f"{ligne['total_du']:,}".replace(',', ' '),
                f"{ligne['total_paye']:,}".replace(',', ' '),
                f"{ligne['reste']:,}".replace(',', ' '),
            ])

        # Construire la table pour la classe
        col_widths = [4.5*cm] + [2.9*cm] * 8
        table = Table(data, repeatRows=1, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('ALIGN', (1,1), (-1,-1), 'RIGHT'),
            ('ALIGN', (0,0), (0,-1), 'LEFT'),
            ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 1),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 0.6*cm))

    # Construire le document avec en-tête + filigrane logo
    doc.build(elements, onFirstPage=_draw_header_and_watermark, onLaterPages=_draw_header_and_watermark)
    return response

@login_required
def export_tranches_par_classe_excel(request):
    """Export Excel (XLSX) des tranches par classe, inscription et réinscription séparées.

    Filtres GET facultatifs: ecole, classe/classe_id, annee_scolaire.
    Respecte la séparation par école pour non-admin.
    """
    # Contrôle d'accès
    is_admin = user_is_admin(request.user)
    is_comptable = False
    try:
        if hasattr(request.user, 'profil'):
            is_comptable = (getattr(request.user.profil, 'role', None) == 'COMPTABLE')
    except Exception:
        is_comptable = False
    if not (is_admin or is_comptable):
        return HttpResponseForbidden("Accès refusé: vous n'avez pas l'autorisation d'exporter ce rapport.")

    # Import openpyxl
    try:
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter
    except Exception:
        return HttpResponse("OpenPyXL n'est pas installé. Veuillez exécuter: pip install openpyxl", status=500)

    raw_ecole = (request.GET.get('ecole') or '').strip()
    raw_classe = (request.GET.get('classe') or request.GET.get('classe_id') or '').strip()
    annee_scolaire = (request.GET.get('annee_scolaire') or '').strip()

    def parse_int(value):
        try:
            return int(value)
        except Exception:
            return None

    ecole_id = parse_int(raw_ecole) if raw_ecole else None
    classe_id = parse_int(raw_classe) if raw_classe else None

    classes = Classe.objects.select_related('ecole').all()
    ecole_user = user_school(request.user)
    annee_active_xl = get_annee_active(request, ecole_user) if ecole_user else None
    restreindre = not user_is_admin(request.user) and ecole_user is not None
    if restreindre:
        classes = classes.filter(ecole=ecole_user)
    elif ecole_id:
        classes = classes.filter(ecole_id=ecole_id)
    if classe_id:
        classes = classes.filter(id=classe_id)
    if annee_active_xl and not annee_scolaire:
        classes = classes.filter(annee_scolaire=annee_active_xl)
    elif annee_scolaire:
        classes = classes.filter(annee_scolaire=annee_scolaire)
    classes = classes.order_by('ecole__nom', 'niveau', 'nom')[:200]

    wb = Workbook()
    ws_index = wb.active
    ws_index.title = 'Index'
    ws_index.append(['Tranches par classe', f"Année: {annee_scolaire}" if annee_scolaire else ''])
    ws_index.append(['Écoles / Classes listées:'])

    headers = TRANCHES_EXPORT_HEADERS

    for classe in classes:
        sheet_name = f"{classe.nom[:25]}"  # Limite Excel <=31
        ws = wb.create_sheet(title=sheet_name)
        ws.append([f"Classe: {classe.nom} – {getattr(classe.ecole, 'nom', '')}"])
        ws.append(headers)

        eleves_mgr = getattr(classe, 'eleves', None)
        eleves = eleves_mgr.all().order_by('nom', 'prenom') if eleves_mgr is not None else []

        for e in eleves:
            ligne = _donnees_tranches_eleve(e, annee_scolaire)

            ws.append([
                getattr(e, 'nom_complet', f"{e.prenom} {e.nom}"),
                int(ligne['inscription']),
                int(ligne['reinscription']),
                int(ligne['tranche_1']),
                int(ligne['tranche_2']),
                int(ligne['tranche_3']),
                int(ligne['total_du']),
                int(ligne['total_paye']),
                int(ligne['reste']),
            ])

        # Ajuster largeur colonnes simple
        for col in range(1, 10):
            ws.column_dimensions[get_column_letter(col)].width = 22 if col == 1 else 16

        # Index line
        ws_index.append([getattr(classe.ecole, 'nom', ''), classe.nom, sheet_name])

    # Supprimer la feuille par défaut si vide
    if ws_index.max_row == 2:
        ws_index.append(['Aucune classe'])

    from io import BytesIO
    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)

    resp = HttpResponse(stream.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    suffix = datetime.now().strftime('%Y%m%d')
    filename = f'tranches_par_classe_{suffix}.xlsx'
    resp['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp
