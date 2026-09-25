"""Documents PDF de paie repris du classeur Excel mensuel.

* état de salaire détaillé par catégorie (feuilles « Direction », « Diécké P »,
  « Etat ») avec les six primes ;
* état du secondaire (feuille « Etat Prof final ») avec les heures ;
* masse salariale (feuille « Masse Salariale ») ;
* fiche d'émargement pour acquis (feuilles « Acquis »).
"""

from decimal import Decimal

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ecole_moderne.branding import get_pdf_palette

from .lettres import montant_en_lettres
from .models import CategoriePaie
from .services import etats_par_categorie, totaux_etats

MOIS = (
    '', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet',
    'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
)


def gnf(valeur):
    return f"{Decimal(valeur or 0):,.0f}".replace(',', ' ')


def heures(valeur):
    if valeur is None:
        return ''
    return f"{Decimal(valeur):.2f}".rstrip('0').rstrip('.')


def nom_affiche(enseignant):
    return f"{enseignant.prenoms} {enseignant.nom}".strip()


def mois_periode(periode):
    return f"{MOIS[periode.mois]} {periode.annee}"


def reponse_pdf(nom_fichier):
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nom_fichier}"'
    return response


class DocumentPaie:
    """Mise en page commune : en-tête de l'école, titre, signatures."""

    def __init__(self, response, periode, titre, paysage=False):
        self.periode = periode
        self.ecole = periode.ecole
        self.titre = titre
        self.palette = get_pdf_palette(self.ecole)
        self.pagesize = landscape(A4) if paysage else A4
        self.doc = SimpleDocTemplate(
            response,
            pagesize=self.pagesize,
            leftMargin=1.2 * cm,
            rightMargin=1.2 * cm,
            topMargin=3.2 * cm,
            bottomMargin=1.5 * cm,
            title=titre,
        )
        styles = getSampleStyleSheet()
        self.style_titre = ParagraphStyle(
            'TitrePaie', parent=styles['Title'], fontSize=14,
            textColor=self.palette.get('primary', colors.black), spaceAfter=4,
        )
        self.style_sous_titre = ParagraphStyle(
            'SousTitrePaie', parent=styles['Normal'], fontSize=10,
            alignment=1, spaceAfter=10,
        )
        self.style_section = ParagraphStyle(
            'SectionPaie', parent=styles['Heading3'], fontSize=11,
            textColor=self.palette.get('primary', colors.black),
            spaceBefore=8, spaceAfter=4,
        )
        self.style_texte = ParagraphStyle(
            'TextePaie', parent=styles['Normal'], fontSize=9, leading=12,
        )
        self.style_cellule = ParagraphStyle(
            'CellulePaie', parent=styles['Normal'], fontSize=7.5, leading=9,
        )
        self.style_entete_colonne = ParagraphStyle(
            'EnteteColonnePaie', parent=self.style_cellule,
            fontName='Helvetica-Bold', alignment=1, fontSize=7, leading=8.5,
            textColor=self.palette.get('header_text', colors.black),
        )
        self._arrete = None
        self.elements = [
            Paragraph(titre, self.style_titre),
            Paragraph(f"Mois de : <b>{mois_periode(periode)}</b>", self.style_sous_titre),
        ]

    def _entete(self, canvas, doc):
        largeur, hauteur = self.pagesize
        canvas.saveState()
        canvas.setFillColor(self.palette.get('primary', colors.black))
        canvas.setFont('Helvetica-Bold', 11)
        canvas.drawString(doc.leftMargin, hauteur - 1.2 * cm, self.ecole.nom or '')
        canvas.setFillColor(colors.black)
        canvas.setFont('Helvetica', 8)
        y = hauteur - 1.65 * cm
        for ligne in (
            getattr(self.ecole, 'adresse', ''),
            f"Tél : {self.ecole.telephone}" if getattr(self.ecole, 'telephone', '') else '',
        ):
            if ligne:
                canvas.drawString(doc.leftMargin, y, ligne[:90])
                y -= 0.38 * cm
        droite = largeur - doc.rightMargin
        canvas.setFont('Helvetica-Bold', 9)
        canvas.drawRightString(droite, hauteur - 1.2 * cm, 'RÉPUBLIQUE DE GUINÉE')
        canvas.setFont('Helvetica-Oblique', 8)
        canvas.drawRightString(droite, hauteur - 1.6 * cm, 'Travail – Justice – Solidarité')
        canvas.setStrokeColor(self.palette.get('primary', colors.black))
        canvas.line(doc.leftMargin, hauteur - 2.6 * cm, droite, hauteur - 2.6 * cm)
        canvas.setFont('Helvetica', 7)
        canvas.drawRightString(
            droite, 0.8 * cm,
            f"Édité le {timezone.localtime():%d/%m/%Y à %H:%M} — page {doc.page}",
        )
        canvas.restoreState()

    def tableau(self, lignes, largeurs, lignes_total=(), aligner_depuis=4,
                hauteur_ligne=None):
        hauteurs = None
        if hauteur_ligne:
            hauteurs = [None] + [hauteur_ligne] * (len(lignes) - 1)
        lignes = [
            [Paragraph(titre, self.style_entete_colonne) for titre in lignes[0]],
            *lignes[1:],
        ]
        table = Table(lignes, colWidths=largeurs, rowHeights=hauteurs, repeatRows=1)
        style = [
            ('BACKGROUND', (0, 0), (-1, 0), self.palette.get('header', colors.lightgrey)),
            ('TEXTCOLOR', (0, 0), (-1, 0), self.palette.get('header_text', colors.black)),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (aligner_depuis, 1), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        for index in lignes_total:
            style += [
                ('FONTNAME', (0, index), (-1, index), 'Helvetica-Bold'),
                ('BACKGROUND', (0, index), (-1, index), colors.HexColor('#EEEEEE')),
            ]
        table.setStyle(TableStyle(style))
        return table

    def arrete(self, libelle, montant):
        # Imprimé avec les signatures pour ne jamais rester seul sur une page.
        self._arrete = Paragraph(
            f"Arrêté {libelle} du mois de {mois_periode(self.periode)} à la somme de : "
            f"<b>{montant_en_lettres(montant)} ({gnf(montant)} GNF)</b>.",
            self.style_texte,
        )

    def signatures(self, titres=('Le Fondateur', 'Le Directeur Général', 'Le Comptable')):
        lieu = (getattr(self.ecole, 'adresse', '') or '').split(',')[0].strip()
        date_texte = f"{lieu + ', ' if lieu else ''}le {timezone.localdate():%d/%m/%Y}"
        largeur = (self.pagesize[0] - 2.4 * cm) / len(titres)
        bloc = Table(
            [[date_texte if i == len(titres) - 1 else '' for i in range(len(titres))],
             list(titres), [''] * len(titres)],
            colWidths=[largeur] * len(titres),
            rowHeights=[0.6 * cm, 0.6 * cm, 1.8 * cm],
        )
        bloc.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        fin = [Spacer(1, 0.3 * cm)]
        if self._arrete is not None:
            fin += [self._arrete, Spacer(1, 0.4 * cm)]
        self.elements.append(KeepTogether(fin + [bloc]))

    def construire(self):
        self.doc.build(self.elements, onFirstPage=self._entete, onLaterPages=self._entete)


# --------------------------------------------------------------------------
# États de salaire
# --------------------------------------------------------------------------

ENTETE_PRIMES = ('Fonct.', 'Craie', 'Ancien.', 'Éloign.', 'Perf.', 'Except.')
CHAMPS_PRIMES_TABLEAU = (
    'prime_fonction', 'prime_craie', 'prime_anciennete',
    'prime_eloignement', 'prime_performance', 'prime_exceptionnelle',
)


def _tableau_fixe(document, groupe):
    """Tableau « Direction / Primaire » : salaire de base + six primes."""
    lignes = [
        ['N°', 'Prénoms et nom', 'Matri.', 'Charge ou fonction', 'Jours',
         'Salaire de base', *ENTETE_PRIMES, 'Salaire brut', 'Retenues',
         'Acompte payé', 'Net à payer', 'Émarg.'],
    ]
    for numero, etat in enumerate(groupe['etats'], start=1):
        enseignant = etat.enseignant
        autres_primes = etat.prime_professeur_principal + etat.prime_revision
        lignes.append([
            numero,
            Paragraph(nom_affiche(enseignant), document.style_cellule),
            enseignant.matricule,
            Paragraph(enseignant.libelle_fonction, document.style_cellule),
            etat.jours_travailles,
            gnf(etat.salaire_base),
            *[gnf(getattr(etat, champ)) for champ in CHAMPS_PRIMES_TABLEAU[:-1]],
            gnf(etat.prime_exceptionnelle + autres_primes),
            gnf(etat.salaire_brut),
            gnf(etat.total_retenues),
            gnf(etat.avances),
            gnf(etat.salaire_net),
            '',
        ])
    t = groupe['totaux']
    lignes.append([
        '', 'TOTAL', '', '', '', gnf(t['salaire_base']),
        *[gnf(t[champ]) for champ in CHAMPS_PRIMES_TABLEAU[:-1]],
        gnf(t['prime_exceptionnelle'] + t['prime_professeur_principal'] + t['prime_revision']),
        gnf(t['brut']), gnf(t['retenues']), gnf(t['avances']), gnf(t['net']), '',
    ])
    largeurs = [0.7, 3.4, 1.5, 2.5, 1.0, 1.7] + [1.4] * 6 + [1.8, 1.5, 1.6, 1.8, 1.2]
    return document.tableau(lignes, [l * cm for l in largeurs], [len(lignes) - 1])


def _tableau_secondaire(document, groupe):
    """Tableau « Etat Prof final » : heures prestées × taux + primes."""
    lignes = [
        ['N°', 'Prénoms et nom', 'Matri.', 'Matière / fonction', 'H. à prester',
         'H. absence', 'H. prestées', 'Taux', 'Valeur des heures',
         'H. révision', 'Primes', 'Salaire brut', 'Retenues', 'Acompte payé',
         'Net à payer', 'Émarg.'],
    ]
    for numero, etat in enumerate(groupe['etats'], start=1):
        enseignant = etat.enseignant
        lignes.append([
            numero,
            Paragraph(nom_affiche(enseignant), document.style_cellule),
            enseignant.matricule,
            Paragraph(enseignant.libelle_fonction, document.style_cellule),
            heures(etat.heures_a_prester),
            heures(etat.heures_absence) if etat.heures_absence else '',
            heures(etat.total_heures),
            gnf(etat.taux_horaire_applique),
            gnf(etat.salaire_base),
            heures(etat.heures_revision) if etat.heures_revision else '',
            gnf(etat.primes),
            gnf(etat.salaire_brut),
            gnf(etat.total_retenues),
            gnf(etat.avances),
            gnf(etat.salaire_net),
            '',
        ])
    t = groupe['totaux']
    total_heures = sum((e.total_heures or Decimal('0') for e in groupe['etats']), Decimal('0'))
    lignes.append([
        '', 'TOTAL', '', '', '', '', heures(total_heures), '', gnf(t['salaire_base']),
        '', gnf(t['primes']), gnf(t['brut']), gnf(t['retenues']),
        gnf(t['avances']), gnf(t['net']), '',
    ])
    largeurs = [0.7, 3.6, 1.5, 2.6, 1.3, 1.2, 1.3, 1.3, 1.9, 1.2, 1.7, 1.9, 1.5, 1.6, 1.9, 1.4]
    return document.tableau(lignes, [l * cm for l in largeurs], [len(lignes) - 1])


def pdf_etat_salaire(periode, categorie=None):
    """État de salaire à payer, par catégorie ou pour tout le personnel."""
    groupes = etats_par_categorie(periode, categorie)
    if categorie:
        libelle = CategoriePaie(categorie).label
        titre = f"ÉTAT DE SALAIRE À PAYER — {libelle.upper()}"
    else:
        titre = "ÉTAT DE SALAIRE À PAYER — PERSONNEL"
    suffixe = (categorie or 'personnel').lower()
    response = reponse_pdf(f"etat_salaire_{suffixe}_{periode.mois:02d}_{periode.annee}.pdf")
    document = DocumentPaie(response, periode, titre, paysage=True)

    if not groupes:
        document.elements.append(Paragraph(
            "Aucun état de salaire n'a encore été calculé pour cette sélection.",
            document.style_texte,
        ))
    for groupe in groupes:
        bloc = []
        if not categorie:
            bloc.append(Paragraph(groupe['libelle'], document.style_section))
        if groupe['categorie'] == CategoriePaie.SECONDAIRE:
            bloc.append(_tableau_secondaire(document, groupe))
        else:
            bloc.append(_tableau_fixe(document, groupe))
        # Un groupe court reste sur une seule page ; un long se découpe normalement.
        document.elements.append(KeepTogether(bloc))

    total = totaux_etats(e for g in groupes for e in g['etats'])
    document.arrete("le présent état de salaire", total['net'])
    document.signatures()
    document.construire()
    return response


def pdf_masse_salariale(periode):
    groupes = etats_par_categorie(periode)
    response = reponse_pdf(f"masse_salariale_{periode.mois:02d}_{periode.annee}.pdf")
    document = DocumentPaie(response, periode, "MASSE SALARIALE")
    lignes = [['N°', 'Catégorie', 'Effectif', 'Montant brut', 'Retenues',
               'Acompte', 'Net à payer', 'Observation']]
    for numero, groupe in enumerate(groupes, start=1):
        t = groupe['totaux']
        lignes.append([
            numero, groupe['libelle'], t['effectif'], gnf(t['brut']),
            gnf(t['retenues']), gnf(t['avances']), gnf(t['net']), '',
        ])
    total = totaux_etats(e for g in groupes for e in g['etats'])
    lignes.append([
        '', 'TOTAL', total['effectif'], gnf(total['brut']), gnf(total['retenues']),
        gnf(total['avances']), gnf(total['net']), '',
    ])
    largeurs = [0.8, 4.4, 1.5, 2.5, 2.0, 2.2, 2.5, 2.7]
    document.elements.append(document.tableau(
        lignes, [l * cm for l in largeurs], [len(lignes) - 1], aligner_depuis=2,
    ))
    document.arrete("la présente masse salariale", total['brut'])
    document.signatures(('La Fondation', 'Le Chargé des finances'))
    document.construire()
    return response


def pdf_emargement(periode, categorie=None):
    """Fiche d'émargement « pour acquis » signée à la remise du salaire."""
    groupes = etats_par_categorie(periode, categorie)
    suffixe = (categorie or 'personnel').lower()
    response = reponse_pdf(f"emargement_{suffixe}_{periode.mois:02d}_{periode.annee}.pdf")
    document = DocumentPaie(
        response, periode, "FICHE D'ÉMARGEMENT DES SALAIRES POUR ACQUIS",
    )
    document.elements.append(Paragraph(
        "1- En émargeant la présente fiche, vous attestez avoir perçu votre salaire "
        f"du mois que vous doit {periode.ecole.nom}.<br/>"
        "2- Le bulletin de paie fournit tous les détails relatifs à votre salaire ; "
        "ce bulletin est personnel.",
        document.style_texte,
    ))
    document.elements.append(Spacer(1, 0.4 * cm))
    lignes = [['N°', 'Prénoms et nom', 'Matri.', 'Site', 'Charge ou fonction',
               'Émargement', 'Observation']]
    numero = 0
    for groupe in groupes:
        for etat in groupe['etats']:
            numero += 1
            lignes.append([
                numero,
                Paragraph(nom_affiche(etat.enseignant), document.style_cellule),
                etat.enseignant.matricule,
                Paragraph(groupe['libelle'], document.style_cellule),
                Paragraph(etat.enseignant.libelle_fonction, document.style_cellule),
                '', '',
            ])
    largeurs = [0.8, 4.2, 1.8, 2.6, 3.4, 3.0, 2.8]
    document.elements.append(document.tableau(
        lignes, [l * cm for l in largeurs], aligner_depuis=7,
        hauteur_ligne=0.9 * cm,
    ))
    document.signatures(('La Fondation', 'Le Comptable'))
    document.construire()
    return response
