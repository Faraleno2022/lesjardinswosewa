"""Carnet PDF professionnel des paiements de scolarité d'un élève."""

from decimal import Decimal
from io import BytesIO
import os
import re

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ecole_moderne.pdf_utils import draw_logo_watermark
from ecole_moderne.branding import get_pdf_palette

from .allocation import (
    allocate_amount_sequentially,
    allocate_discounts,
    due_balances,
)
from .calculs import filtre_types_scolarite
from .models import EcheancierPaiement, Paiement


MOIS_FR = (
    '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
    'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
)


def _decimal(value):
    return Decimal(str(value or 0))


def _format_gnf(value):
    return f"{_decimal(value):,.0f}".replace(',', ' ')


def _logo_path(ecole):
    try:
        path = getattr(getattr(ecole, 'logo', None), 'path', None)
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return finders.find('logos/logo.png')


def collecter_carnet_paiement(paiement):
    """Reconstruit le solde après chaque paiement validé de l'année."""
    ecole = paiement.ecole_reference
    echeancier = EcheancierPaiement.objects.filter(
        eleve=paiement.eleve,
        annee_scolaire=paiement.annee_scolaire,
    ).first()

    paiements = Paiement.objects.filter(
        eleve=paiement.eleve,
        annee_scolaire=paiement.annee_scolaire,
        statut='VALIDE',
    ).filter(filtre_types_scolarite())
    if ecole is not None:
        paiements = paiements.pour_ecole(ecole)
    paiements = list(
        paiements.select_related('type_paiement').prefetch_related(
            'remises'
        ).order_by('date_paiement', 'date_creation', 'pk')
    )

    total_du = _decimal(echeancier.total_du) if echeancier else None
    soldes = due_balances(echeancier) if echeancier else None
    lignes = []
    total_encaisse = Decimal('0')
    total_remises = Decimal('0')

    for versement in paiements:
        total_encaisse += _decimal(versement.montant)
        reste = None
        if echeancier is not None:
            allocation_remise, apres_remises = allocate_discounts(
                echeancier,
                list(versement.remises.all()),
                balances=soldes,
            )
            total_remises += sum(
                allocation_remise.values(), Decimal('0')
            )
            _, soldes, _ = allocate_amount_sequentially(
                versement.montant, apres_remises
            )
            reste = sum(soldes.values(), Decimal('0'))

        lignes.append({
            'mois': f"{MOIS_FR[versement.date_paiement.month]} "
                    f"{versement.date_paiement.year}",
            'date': versement.date_paiement,
            'numero_recu': versement.numero_recu,
            'montant': _decimal(versement.montant),
            'reste': reste,
        })

    return {
        'ecole': ecole,
        'eleve': paiement.eleve,
        'classe': paiement.classe_reference,
        'annee_scolaire': paiement.annee_scolaire,
        'lignes': lignes,
        'total_du': total_du,
        'total_encaisse': total_encaisse,
        'total_remises': total_remises,
        'reste_final': (
            sum(soldes.values(), Decimal('0'))
            if soldes is not None else None
        ),
    }


def construire_carnet_paiement_pdf(paiement):
    """Retourne le PDF du carnet sous forme de bytes."""
    donnees = collecter_carnet_paiement(paiement)
    ecole = donnees['ecole']
    eleve = donnees['eleve']
    palette = get_pdf_palette(ecole)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.2 * cm,
        rightMargin=1.2 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.35 * cm,
        title=f"Carnet de paiement - {eleve.nom_complet}",
        author=getattr(ecole, 'nom', '') or 'Établissement scolaire',
    )

    styles = getSampleStyleSheet()
    titre = ParagraphStyle(
        'CarnetTitre',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=20,
        textColor=palette['primary'],
        alignment=TA_CENTER,
        spaceAfter=3,
    )
    sous_titre = ParagraphStyle(
        'CarnetSousTitre',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=palette['muted'],
        alignment=TA_CENTER,
    )
    libelle = ParagraphStyle(
        'CarnetLibelle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        textColor=palette['muted'],
    )
    valeur = ParagraphStyle(
        'CarnetValeur',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=palette['text'],
    )
    cellule = ParagraphStyle(
        'CarnetCellule',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=TA_LEFT,
    )
    cellule_centre = ParagraphStyle(
        'CarnetCelluleCentre',
        parent=cellule,
        alignment=TA_CENTER,
    )
    cellule_entete = ParagraphStyle(
        'CarnetCelluleEntete',
        parent=cellule_centre,
        fontName='Helvetica-Bold',
        textColor=palette['header_text'],
    )

    elements = []
    logo = _logo_path(ecole)
    logo_flowable = ''
    if logo:
        try:
            logo_flowable = Image(logo, width=2.1 * cm, height=2.1 * cm)
        except Exception:
            logo_flowable = ''

    coordonnees = []
    for texte in (
        getattr(ecole, 'adresse', '') if ecole else '',
        f"Tél. : {getattr(ecole, 'telephone', '')}" if ecole and getattr(ecole, 'telephone', '') else '',
        getattr(ecole, 'email', '') if ecole else '',
    ):
        if texte:
            coordonnees.append(str(texte))
    identite = [
        Paragraph(getattr(ecole, 'nom', '') or 'ÉTABLISSEMENT SCOLAIRE', titre),
        Paragraph('<br/>'.join(coordonnees), sous_titre),
    ]
    entete = Table(
        [[logo_flowable, identite]],
        colWidths=[2.7 * cm, 15.9 * cm],
    )
    entete.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.extend([
        entete,
        Spacer(1, 0.35 * cm),
        Paragraph('CARNET DE PAIEMENT SCOLAIRE', titre),
        Paragraph(
            "Historique officiel des versements et du reste à payer",
            sous_titre,
        ),
        Spacer(1, 0.35 * cm),
    ])

    informations = Table([
        [Paragraph('ÉLÈVE', libelle), Paragraph(eleve.nom_complet, valeur),
         Paragraph('MATRICULE', libelle), Paragraph(eleve.matricule or '—', valeur)],
        [Paragraph('CLASSE', libelle), Paragraph(str(donnees['classe'] or '—'), valeur),
         Paragraph('ANNÉE SCOLAIRE', libelle), Paragraph(donnees['annee_scolaire'] or '—', valeur)],
    ], colWidths=[2.3 * cm, 6.7 * cm, 2.8 * cm, 6.8 * cm])
    informations.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['table_light']),
        ('BOX', (0, 0), (-1, -1), 0.7, palette['border']),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.extend([informations, Spacer(1, 0.35 * cm)])

    def montant_ou_tiret(value):
        return f"{_format_gnf(value)} GNF" if value is not None else 'Non configuré'

    resume = Table([
        [Paragraph('TOTAL À PAYER', libelle),
         Paragraph(montant_ou_tiret(donnees['total_du']), valeur),
         Paragraph('TOTAL VERSÉ', libelle),
         Paragraph(f"{_format_gnf(donnees['total_encaisse'])} GNF", valeur)],
        [Paragraph('REMISES', libelle),
         Paragraph(f"{_format_gnf(donnees['total_remises'])} GNF", valeur),
         Paragraph('RESTE À PAYER', libelle),
         Paragraph(montant_ou_tiret(donnees['reste_final']), valeur)],
    ], colWidths=[2.7 * cm, 6.3 * cm, 2.7 * cm, 6.9 * cm])
    resume.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['surface']),
        ('BOX', (0, 0), (-1, -1), 0.7, palette['border']),
        ('INNERGRID', (0, 0), (-1, -1), 0.35, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    elements.extend([resume, Spacer(1, 0.45 * cm)])

    tableau = [[
        Paragraph('MOIS', cellule_entete),
        Paragraph('DATE', cellule_entete),
        Paragraph('MONTANT', cellule_entete),
        Paragraph('RESTE À PAYER', cellule_entete),
        Paragraph('SIGNATURE COMPTABLE', cellule_entete),
    ]]
    for ligne in donnees['lignes']:
        date_recu = (
            f"{ligne['date']:%d/%m/%Y}<br/>"
            f"<font size='7' color='#667788'>{ligne['numero_recu']}</font>"
        )
        tableau.append([
            Paragraph(ligne['mois'], cellule),
            Paragraph(date_recu, cellule_centre),
            Paragraph(f"{_format_gnf(ligne['montant'])} GNF", cellule_centre),
            Paragraph(montant_ou_tiret(ligne['reste']), cellule_centre),
            Paragraph('<br/><br/>', cellule_centre),
        ])

    if len(tableau) == 1:
        tableau.append([
            Paragraph('—', cellule_centre),
            Paragraph('—', cellule_centre),
            Paragraph('Aucun versement de scolarité validé', cellule_centre),
            Paragraph(montant_ou_tiret(donnees['reste_final']), cellule_centre),
            Paragraph('', cellule_centre),
        ])

    historique = Table(
        tableau,
        colWidths=[3.2 * cm, 3.0 * cm, 3.8 * cm, 4.0 * cm, 4.6 * cm],
        rowHeights=[0.85 * cm] + [1.55 * cm] * (len(tableau) - 1),
        repeatRows=1,
    )
    style_tableau = [
        ('BACKGROUND', (0, 0), (-1, 0), palette['header']),
        ('TEXTCOLOR', (0, 0), (-1, 0), palette['header_text']),
        ('BOX', (0, 0), (-1, -1), 0.8, palette['border']),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, palette['border']),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for index in range(1, len(tableau)):
        if index % 2 == 0:
            style_tableau.append(
                ('BACKGROUND', (0, index), (-1, index), palette['table_light'])
            )
    historique.setStyle(TableStyle(style_tableau))
    elements.extend([
        historique,
        Spacer(1, 0.35 * cm),
        Paragraph(
            "Chaque ligne doit être visée par le service comptable. Les montants "
            "et soldes proviennent des paiements de scolarité validés dans le logiciel.",
            sous_titre,
        ),
    ])

    def decorer_page(pdf, document):
        pdf.saveState()
        try:
            draw_logo_watermark(pdf, A4[0], A4[1], ecole=ecole)
        except Exception:
            pass
        pdf.setStrokeColor(palette['border'])
        pdf.line(1.2 * cm, 0.95 * cm, A4[0] - 1.2 * cm, 0.95 * cm)
        pdf.setFillColor(palette['muted'])
        pdf.setFont('Helvetica', 7)
        pdf.drawString(
            1.2 * cm,
            0.62 * cm,
            f"Généré le {timezone.localtime():%d/%m/%Y à %H:%M}",
        )
        pdf.drawRightString(
            A4[0] - 1.2 * cm,
            0.62 * cm,
            f"Page {document.page}",
        )
        pdf.restoreState()

    doc.build(elements, onFirstPage=decorer_page, onLaterPages=decorer_page)
    return buffer.getvalue()


def nom_fichier_carnet(paiement):
    identifiant = paiement.eleve.matricule or paiement.eleve.nom_complet
    identifiant = re.sub(r'[^A-Za-z0-9_-]+', '_', identifiant).strip('_')
    annee = re.sub(r'[^0-9-]+', '', paiement.annee_scolaire or '')
    return f"Carnet_paiement_{identifiant or paiement.eleve_id}_{annee}.pdf"
