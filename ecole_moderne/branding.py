"""Palette graphique centralisee et securisee pour chaque ecole."""

import re


HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

DEFAULT_BRANDING = {
    'primary': '#163B65',
    'secondary': '#2F75B5',
    'accent': '#F2B134',
    'success': '#198754',
    'warning': '#F59E0B',
    'danger': '#DC3545',
    'info': '#0EA5E9',
    'surface': '#F5F8FB',
    'text': '#172B3A',
    'border': '#AFC3D6',
}

SCHOOL_COLOR_FIELDS = {
    'primary': 'couleur_primaire',
    'secondary': 'couleur_secondaire',
    'accent': 'couleur_accent',
    'success': 'couleur_succes',
    'warning': 'couleur_avertissement',
    'danger': 'couleur_danger',
    'info': 'couleur_information',
    'surface': 'couleur_fond_documents',
    'text': 'couleur_texte_documents',
    'border': 'couleur_bordure_documents',
}


def normaliser_couleur(value, fallback):
    value = str(value or '').strip()
    return value.upper() if HEX_COLOR_RE.fullmatch(value) else fallback


def melanger_couleurs(base, cible, proportion):
    """Melange deux couleurs hexadecimales, proportion allant de 0 a 1."""
    base = normaliser_couleur(base, '#000000')
    cible = normaliser_couleur(cible, '#FFFFFF')
    proportion = max(0.0, min(1.0, float(proportion)))
    valeurs = []
    for index in (1, 3, 5):
        depart = int(base[index:index + 2], 16)
        arrivee = int(cible[index:index + 2], 16)
        valeurs.append(round(depart + (arrivee - depart) * proportion))
    return '#{:02X}{:02X}{:02X}'.format(*valeurs)


def couleur_contraste(couleur):
    couleur = normaliser_couleur(couleur, '#000000')
    rouge, vert, bleu = (
        int(couleur[1:3], 16),
        int(couleur[3:5], 16),
        int(couleur[5:7], 16),
    )
    luminance = (0.299 * rouge + 0.587 * vert + 0.114 * bleu) / 255
    return '#172B3A' if luminance > 0.64 else '#FFFFFF'


def couleur_rgb(couleur):
    couleur = normaliser_couleur(couleur, '#000000')
    return ', '.join(str(int(couleur[index:index + 2], 16)) for index in (1, 3, 5))


def _completer_palette(palette):
    resultat = dict(palette)
    for nom in ('primary', 'secondary', 'accent', 'success', 'warning', 'danger', 'info'):
        resultat[f'{nom}_dark'] = melanger_couleurs(resultat[nom], '#000000', 0.22)
        resultat[f'{nom}_light'] = melanger_couleurs(resultat[nom], '#FFFFFF', 0.88)
        resultat[f'{nom}_text'] = couleur_contraste(resultat[nom])
        resultat[f'{nom}_rgb'] = couleur_rgb(resultat[nom])
    resultat['surface_alt'] = melanger_couleurs(resultat['surface'], '#FFFFFF', 0.45)
    resultat['muted'] = melanger_couleurs(resultat['text'], '#FFFFFF', 0.42)
    resultat['header'] = resultat['primary']
    resultat['header_text'] = couleur_contraste(resultat['header'])
    resultat['table_light'] = resultat['primary_light']
    return resultat


def get_school_branding(ecole=None):
    palette = dict(DEFAULT_BRANDING)
    if ecole is not None:
        for nom, champ in SCHOOL_COLOR_FIELDS.items():
            palette[nom] = normaliser_couleur(
                getattr(ecole, champ, None),
                DEFAULT_BRANDING[nom],
            )
    return _completer_palette(palette)


def get_document_branding(ecole=None, *, bulletin=False):
    """Retourne la palette generale ou la surcharge active des bulletins."""
    palette = get_school_branding(ecole)
    if not bulletin or ecole is None:
        return palette

    try:
        from notes.models import ThemeBulletin

        theme = ThemeBulletin.objects.filter(ecole=ecole, actif=True).order_by(
            '-par_defaut', '-date_modification', '-pk'
        ).first()
    except Exception:
        theme = None

    if theme is None:
        return palette

    palette.update({
        'primary': normaliser_couleur(theme.couleur_primaire, palette['primary']),
        'secondary': normaliser_couleur(theme.couleur_secondaire, palette['secondary']),
        'accent': normaliser_couleur(theme.couleur_accent, palette['accent']),
        'text': normaliser_couleur(theme.couleur_texte_principal, palette['text']),
        'muted': normaliser_couleur(theme.couleur_texte_secondaire, palette['muted']),
        'header': normaliser_couleur(theme.couleur_fond_header, palette['header']),
        'table_light': normaliser_couleur(theme.couleur_fond_tableau, palette['table_light']),
        'surface': normaliser_couleur(theme.couleur_fond_carte, palette['surface']),
        'border': normaliser_couleur(theme.couleur_bordure, palette['border']),
        'mention_tb': normaliser_couleur(theme.couleur_mention_tb, palette['success']),
        'mention_bien': normaliser_couleur(theme.couleur_mention_bien, palette['secondary']),
        'mention_ab': normaliser_couleur(theme.couleur_mention_ab, palette['warning']),
        'mention_passable': normaliser_couleur(theme.couleur_mention_passable, palette['accent']),
        'mention_insuffisant': normaliser_couleur(theme.couleur_mention_insuffisant, palette['danger']),
    })
    palette = _completer_palette(palette)
    palette['header'] = normaliser_couleur(theme.couleur_fond_header, palette['primary'])
    palette['header_text'] = couleur_contraste(palette['header'])
    palette['table_light'] = normaliser_couleur(theme.couleur_fond_tableau, palette['primary_light'])
    palette['mention_tb'] = normaliser_couleur(theme.couleur_mention_tb, palette['success'])
    palette['mention_bien'] = normaliser_couleur(theme.couleur_mention_bien, palette['secondary'])
    palette['mention_ab'] = normaliser_couleur(theme.couleur_mention_ab, palette['warning'])
    palette['mention_passable'] = normaliser_couleur(theme.couleur_mention_passable, palette['accent'])
    palette['mention_insuffisant'] = normaliser_couleur(theme.couleur_mention_insuffisant, palette['danger'])
    palette['muted'] = normaliser_couleur(theme.couleur_texte_secondaire, palette['muted'])
    return palette


def get_pdf_palette(ecole=None, *, bulletin=False):
    from reportlab.lib import colors

    return {
        nom: colors.HexColor(valeur)
        for nom, valeur in get_document_branding(ecole, bulletin=bulletin).items()
        if isinstance(valeur, str) and HEX_COLOR_RE.fullmatch(valeur)
    }
