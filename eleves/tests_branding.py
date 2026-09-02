from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.template import Context, Template
from django.test import TestCase
from reportlab.lib import colors

from ecole_moderne.branding import (
    get_document_branding,
    get_pdf_palette,
    get_school_branding,
)
from notes.models import ThemeBulletin
from utilisateurs.context_processors import user_context

from .models import Ecole


class CharteGraphiqueEcoleTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='École Charte',
            adresse='Conakry',
            telephone='+224622000321',
            directeur='Direction',
            couleur_primaire='#4C1D95',
            couleur_secondaire='#0F766E',
            couleur_accent='#F97316',
            couleur_succes='#15803D',
            couleur_avertissement='#FACC15',
            couleur_danger='#B91C1C',
            couleur_information='#0369A1',
            couleur_fond_documents='#FAF5FF',
            couleur_texte_documents='#1F2937',
            couleur_bordure_documents='#C4B5FD',
        )

    def test_palette_ecole_contient_couleurs_et_variantes_css(self):
        palette = get_school_branding(self.ecole)

        self.assertEqual(palette['primary'], '#4C1D95')
        self.assertEqual(palette['success'], '#15803D')
        self.assertEqual(palette['surface'], '#FAF5FF')
        self.assertEqual(palette['primary_rgb'], '76, 29, 149')
        self.assertRegex(palette['primary_light'], r'^#[0-9A-F]{6}$')
        self.assertEqual(palette['primary_text'], '#FFFFFF')

    def test_couleur_invalide_est_refusee_par_le_modele(self):
        self.ecole.couleur_primaire = 'violet'

        with self.assertRaises(ValidationError):
            self.ecole.full_clean()

    def test_theme_bulletin_actif_surcharge_seulement_les_bulletins(self):
        ThemeBulletin.objects.create(
            nom='Bulletin solaire',
            ecole=self.ecole,
            actif=True,
            par_defaut=True,
            couleur_primaire='#7C3AED',
            couleur_secondaire='#2563EB',
            couleur_accent='#EA580C',
            couleur_fond_header='#FDE047',
            couleur_fond_tableau='#FEF9C3',
            couleur_texte_principal='#111827',
            couleur_texte_secondaire='#4B5563',
        )

        generale = get_document_branding(self.ecole)
        bulletin = get_document_branding(self.ecole, bulletin=True)
        pdf = get_pdf_palette(self.ecole, bulletin=True)

        self.assertEqual(generale['primary'], '#4C1D95')
        self.assertEqual(bulletin['primary'], '#7C3AED')
        self.assertEqual(bulletin['header'], '#FDE047')
        self.assertEqual(bulletin['header_text'], '#172B3A')
        self.assertEqual(bulletin['muted'], '#4B5563')
        self.assertEqual(pdf['header'], colors.HexColor('#FDE047'))

    def test_balise_document_rend_le_theme_disponible_aux_pdf_html(self):
        ThemeBulletin.objects.create(
            ecole=self.ecole,
            nom='HTML PDF',
            actif=True,
            par_defaut=True,
            couleur_primaire='#0F766E',
        )
        rendu = Template(
            '{% load branding %}'
            '{% school_document_branding ecole bulletin=True as palette %}'
            '{{ palette.primary }}'
        ).render(Context({'ecole': self.ecole}))

        self.assertEqual(rendu, '#0F766E')

    @patch('utilisateurs.context_processors.get_user_permissions', return_value={})
    @patch('utilisateurs.context_processors.check_comptable_restrictions', return_value={})
    @patch('eleves.utils_annee.get_annee_active', return_value='2026-2027')
    @patch(
        'eleves.utils_annee.get_statut_creation_nouvelle_annee',
        return_value={'due': False},
    )
    def test_contexte_global_expose_la_charte_de_lecole(
        self,
        _statut,
        _annee,
        _restrictions,
        _permissions,
    ):
        profil = SimpleNamespace(
            ecole=self.ecole,
            role='ADMIN',
        )
        utilisateur = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            profil=profil,
        )
        request = SimpleNamespace(user=utilisateur)

        contexte = user_context(request)

        self.assertEqual(contexte['school_branding']['primary'], '#4C1D95')
        self.assertEqual(contexte['school_branding']['danger'], '#B91C1C')
