"""
Générateur de notes de rappel de paiement en PDF
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from django.conf import settings
from django.db.models import Sum
from datetime import datetime, timedelta
import os
from io import BytesIO
from PIL import Image as PILImage

def generer_note_rappel_eleve(eleve, response=None):
    """Génère une note de rappel pour un élève spécifique"""
    
    if response is None:
        buffer = BytesIO()
    else:
        buffer = response
    
    # Configuration du document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Style pour le titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#000000'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    # Style pour le contenu
    content_style = ParagraphStyle(
        'Content',
        parent=styles['Normal'],
        fontSize=12,
        leading=18,
        alignment=TA_JUSTIFY,
        fontName='Helvetica'
    )
    
    # Style pour les infos
    info_style = ParagraphStyle(
        'Info',
        parent=styles['Normal'],
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        fontName='Helvetica'
    )
    
    elements = []
    
    # Date et lieu (format français, sans balises visibles)
    mois_fr = {
        'January': 'janvier', 'February': 'février', 'March': 'mars', 'April': 'avril',
        'May': 'mai', 'June': 'juin', 'July': 'juillet', 'August': 'août',
        'September': 'septembre', 'October': 'octobre', 'November': 'novembre', 'December': 'décembre',
    }
    maintenant = datetime.now()
    nom_mois_en = maintenant.strftime('%B')
    nom_mois_fr = mois_fr.get(nom_mois_en, nom_mois_en)
    date_text = f"Conakry, le {maintenant.strftime('%d')} {nom_mois_fr} {maintenant.strftime('%Y')}"
    date_para = Paragraph(date_text, info_style)
    elements.append(date_para)
    elements.append(Spacer(1, 12))
    
    # Titre (sans balises HTML)
    elements.append(Paragraph("NOTE DE RAPPEL", title_style))
    elements.append(Spacer(1, 12))
    
    # Logo de l'école (si disponible)
    ecole = eleve.classe.ecole
    logo_path = None
    if ecole.logo and os.path.exists(ecole.logo.path):
        logo_path = ecole.logo.path
        try:
            # Logo d'en-tête plus petit
            img = Image(logo_path, width=25*mm, height=25*mm)
            # Créer un tableau pour centrer l'image
            logo_table = Table([[img]], colWidths=[170*mm])
            logo_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ]))
            elements.append(logo_table)
            elements.append(Spacer(1, 10))
        except:
            logo_path = None
    
    # Calcul des paiements et soldes — utilise l'échéancier réel (source de vérité)
    from paiements.models import Paiement, ConfigurationPaiement, EcheancierPaiement
    from decimal import Decimal

    tranches_payees = []
    tranches_restantes = []
    montant_total = Decimal('0')
    reste_a_payer = Decimal('0')

    # Priorité 1 : utiliser l'échéancier (source de vérité par tranche)
    ech = None
    try:
        ech = eleve.echeancier
    except EcheancierPaiement.DoesNotExist:
        ech = None

    if ech and ech.total_du > 0:
        montant_total = ech.total_du
        reste_a_payer = ech.solde_restant

        # Inscription
        fi_du = Decimal(str(ech.frais_inscription_du or 0))
        fi_paye = Decimal(str(ech.frais_inscription_paye or 0))
        if fi_du > 0:
            fi_reste = max(Decimal('0'), fi_du - fi_paye)
            if fi_reste <= 0:
                tranches_payees.append("Inscription")
            else:
                tranches_restantes.append(f"Inscription ({fi_reste:,.0f} GNF restant)")

        # Tranches 1, 2, 3
        for i, (due_field, paye_field) in enumerate([
            ('tranche_1_due', 'tranche_1_payee'),
            ('tranche_2_due', 'tranche_2_payee'),
            ('tranche_3_due', 'tranche_3_payee'),
        ], start=1):
            t_du = Decimal(str(getattr(ech, due_field, 0) or 0))
            t_paye = Decimal(str(getattr(ech, paye_field, 0) or 0))
            if t_du > 0:
                t_reste = max(Decimal('0'), t_du - t_paye)
                if t_reste <= 0:
                    tranches_payees.append(f"Tranche {i}")
                else:
                    tranches_restantes.append(f"Tranche {i} ({t_reste:,.0f} GNF restant)")

    else:
        # Fallback : utiliser ConfigurationPaiement si pas d'échéancier
        try:
            config = ConfigurationPaiement.objects.get(classe=eleve.classe)
            montant_total = config.montant_inscription + config.montant_scolarite

            total_paye = Paiement.objects.filter(
                eleve=eleve, statut='VALIDE'
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0')
            reste_a_payer = max(Decimal('0'), montant_total - total_paye)

            if reste_a_payer > 0:
                tranches_restantes.append(f"Solde total restant ({reste_a_payer:,.0f} GNF)")
            else:
                tranches_payees.append("Scolarité complète")

        except ConfigurationPaiement.DoesNotExist:
            montant_total = Decimal('0')
            reste_a_payer = Decimal('0')
            tranches_restantes = ["Configuration de paiement non définie"]
    
    # Texte principal (sans balises, sur une seule note compacte)
    texte_principal = (
        f"La Direction du {ecole.nom} vous prie de bien vouloir passer à l'école "
        "pour le paiement des frais de scolarité de votre enfant."
    )
    elements.append(Paragraph(texte_principal, content_style))
    elements.append(Spacer(1, 16))
    
    # Informations de l'élève (sans balises HTML)
    # Calcul du montant déjà payé (séparé pour plus de clarté)
    montant_deja_paye = montant_total - reste_a_payer if montant_total else 0

    info_data = [
        ['Prénoms :', eleve.prenom],
        ['Nom :', eleve.nom],
        ['Classe :', eleve.classe.nom],
        ['Matricule :', eleve.matricule],
        ['', ''],
        ['Montant total des frais :', f"{montant_total:,.0f} GNF" if montant_total else 'Non défini'],
        ['Montant déjà payé :', f"{montant_deja_paye:,.0f} GNF" if montant_total else 'Non défini'],
        ['Reste à payer :', f"{reste_a_payer:,.0f} GNF" if montant_total else 'Non défini'],
        ['', ''],
    ]
    
    # Ajouter les tranches restantes
    if tranches_restantes:
        info_data.append(['Tranches restantes :', ''])
        for tranche in tranches_restantes:
            info_data.append(['', f"• {tranche}"])
    
    # Délai de paiement (prochain vendredi, affiché en français)
    jours_fr = {
        0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi',
        4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche',
    }
    delai = datetime.now() + timedelta(days=7)
    while delai.weekday() != 4:  # 4 = Vendredi
        delai += timedelta(days=1)
    mois_fr = {
        'January': 'janvier', 'February': 'février', 'March': 'mars', 'April': 'avril',
        'May': 'mai', 'June': 'juin', 'July': 'juillet', 'August': 'août',
        'September': 'septembre', 'October': 'octobre', 'November': 'novembre', 'December': 'décembre',
    }
    nom_jour = jours_fr.get(delai.weekday(), delai.strftime('%A'))
    nom_mois_en = delai.strftime('%B')
    nom_mois_fr = mois_fr.get(nom_mois_en, nom_mois_en)
    delai_text = f"{nom_jour} {delai.strftime('%d')} {nom_mois_fr} {delai.strftime('%Y')}"
    
    info_data.append(['', ''])
    info_data.append(['Délai de paiement :', delai_text])
    
    # Créer le tableau des informations (un peu plus compact)
    info_table = Table(info_data, colWidths=[65*mm, 85*mm])
    info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(info_table)
    # Espace réduit pour remonter la signature
    elements.append(Spacer(1, 12))
    
    # Signature
    signature_data = [
        ['', 'La Direction'],
        ['', ''],
        ['', ''],
        ['', '________________'],
    ]
    
    signature_table = Table(signature_data, colWidths=[100*mm, 60*mm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
    ]))
    
    elements.append(signature_table)
    
    # Note de bas de page (sans balises HTML complexes)
    note_text = "NB : Veuillez vous munir de cette note lors du paiement."
    note_style = ParagraphStyle(
        'Note',
        parent=styles['Normal'],
        fontSize=9,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#555555'),
    )
    # Espace réduit pour remonter le NB
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(note_text, note_style))
    
    # Fonction de filigrane avec le logo de l'école
    def _watermark(canvas, doc):
        canvas.saveState()
        if 'logo_path' in locals() and logo_path:
            try:
                # Position au centre de la page
                page_width, page_height = A4
                canvas.translate(page_width / 2, page_height / 2)
                canvas.rotate(30)
                canvas.setFillAlpha(0.06)
                canvas.drawImage(logo_path, -40*mm, -40*mm, width=80*mm, height=80*mm, preserveAspectRatio=True, mask='auto')
            except Exception:
                pass
        canvas.restoreState()
    
    # Construire le PDF avec filigrane
    doc.build(elements, onFirstPage=_watermark, onLaterPages=_watermark)
    
    if response is None:
        buffer.seek(0)
        return buffer
    
    return response


def generer_notes_rappel_classe(classe):
    """Génère les notes de rappel pour tous les élèves d'une classe"""
    from eleves.models import Eleve
    from paiements.models import Paiement, ConfigurationPaiement
    
    # Récupérer tous les élèves actifs de la classe
    eleves = Eleve.objects.filter(
        classe=classe,
        statut='ACTIF'
    ).order_by('nom', 'prenom')
    
    # Filtrer les élèves qui ont un solde impayé
    eleves_avec_impayes = []
    
    try:
        config = ConfigurationPaiement.objects.get(classe=classe)
        montant_total = config.montant_inscription + config.montant_scolarite
        
        for eleve in eleves:
            paiements_effectues = Paiement.objects.filter(
                eleve=eleve,
                statut='VALIDE'
            ).aggregate(total=Sum('montant'))['total'] or 0
            
            reste_a_payer = montant_total - paiements_effectues
            
            if reste_a_payer > 0:
                eleves_avec_impayes.append(eleve)
    except ConfigurationPaiement.DoesNotExist:
        # Si pas de configuration, inclure tous les élèves
        eleves_avec_impayes = list(eleves)
    
    # Créer un PDF avec toutes les notes
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    
    all_elements = []
    
    for i, eleve in enumerate(eleves_avec_impayes):
        # Générer la note pour cet élève
        eleve_buffer = BytesIO()
        generer_note_rappel_eleve(eleve, eleve_buffer)
        
        # Ajouter un saut de page entre les notes (sauf pour la dernière)
        if i < len(eleves_avec_impayes) - 1:
            from reportlab.platypus import PageBreak
            all_elements.append(PageBreak())
    
    # Si on a des éléments, construire le document
    if all_elements:
        doc.build(all_elements)
        buffer.seek(0)
        return buffer, len(eleves_avec_impayes)
    
    return None, 0
