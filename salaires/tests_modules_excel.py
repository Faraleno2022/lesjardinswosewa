"""Modules repris du classeur de paie « 8- Mai.xlsx ».

Les montants attendus reproduisent des lignes réelles du classeur (feuilles
Etat, Etat Prof final, Masse Salariale) pour vérifier que le logiciel donne
les mêmes résultats.
"""

from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from eleves.models import Ecole
from .lettres import montant_en_lettres, nombre_en_lettres
from .models import (
    AvanceSalaire,
    Enseignant,
    ParametresPaie,
    PeriodeSalaire,
    SourceHeuresSalaire,
    TypeEnseignant,
)
from .services import calculer_etat_salaire, heures_emploi_du_temps
from .tests import TEST_MIDDLEWARE


def texte_pdf(response):
    return ''.join(
        page.extract_text() for page in PdfReader(BytesIO(response.content)).pages
    )


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ModulesPaieExcelTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='paie-excel', password='test', email='paie@example.com',
        )
        self.ecole = Ecole.objects.create(
            nom='Groupe scolaire test', adresse='Conakry', telephone='620000002',
            directeur='Direction', etat='VALIDE',
        )
        self.user.profil.ecole = self.ecole
        self.user.profil.save()
        # Mai 2026 : 5 vendredis et 5 samedis, 4 exemplaires des autres jours.
        self.periode = PeriodeSalaire.objects.create(
            ecole=self.ecole, mois=5, annee=2026, cree_par=self.user,
        )
        ParametresPaie.objects.create(
            ecole=self.ecole,
            prime_anciennete_par_an=Decimal('10000'),
            prime_eloignement_par_km=Decimal('2000'),
            retenue_par_jour_chome=Decimal('30000'),
            prime_professeur_principal=Decimal('50000'),
            prime_heure_revision=Decimal('10000'),
        )
        self.client.force_login(self.user)

    def creer_dg(self):
        """Ligne « Hamed BAMBA » de la feuille Etat."""
        return Enseignant.objects.create(
            nom='BAMBA', prenoms='Hamed', matricule='0499120', ecole=self.ecole,
            type_enseignant=TypeEnseignant.ADMINISTRATEUR, fonction='DG',
            salaire_fixe=Decimal('600000'), prime_fonction=Decimal('800000'),
            distance_km=Decimal('15'), date_embauche=date(2021, 1, 1),
            cree_par=self.user,
        )

    def creer_prof(self, **heures):
        """Ligne « Kadiatou DIALLO » de la feuille Etat Prof final."""
        return Enseignant.objects.create(
            nom='DIALLO', prenoms='Kadiatou', matricule='0408219', ecole=self.ecole,
            type_enseignant=TypeEnseignant.SECONDAIRE, fonction='Anglais',
            taux_horaire=Decimal('13500'), date_embauche=date(2026, 1, 5),
            heures_mercredi=Decimal('3'), heures_jeudi=Decimal('3'),
            heures_vendredi=Decimal('4'), cree_par=self.user, **heures,
        )

    def test_primes_automatiques_et_acompte_comme_la_feuille_etat(self):
        dg = self.creer_dg()
        etat, _ = calculer_etat_salaire(dg, self.periode, self.user)
        etat.prime_performance = Decimal('50000')
        etat.prime_exceptionnelle = Decimal('80000')
        etat.save()
        AvanceSalaire.objects.create(
            enseignant=dg, periode=self.periode, montant=Decimal('1575000'),
            date_avance=date(2026, 5, 10), cree_par=self.user,
        )
        etat, _ = calculer_etat_salaire(dg, self.periode, self.user)

        self.assertEqual(etat.prime_fonction, Decimal('800000'))
        self.assertEqual(etat.prime_anciennete, Decimal('50000'))  # 5 ans
        self.assertEqual(etat.prime_eloignement, Decimal('30000'))  # 15 km
        self.assertEqual(etat.salaire_brut, Decimal('1610000'))
        self.assertEqual(etat.salaire_net, Decimal('35000'))

        # Un recalcul conserve les primes du mois et relit la fiche.
        dg.prime_fonction = Decimal('850000')
        dg.save()
        etat, _ = calculer_etat_salaire(dg, self.periode, self.user)
        self.assertEqual(etat.prime_performance, Decimal('50000'))
        self.assertEqual(etat.primes, Decimal('1060000'))

    def test_jours_chomes_retenus_et_jours_travailles(self):
        dg = self.creer_dg()
        etat, _ = calculer_etat_salaire(dg, self.periode, self.user)
        response = self.client.post(
            reverse('salaires:ajuster_etat_salaire', args=[etat.pk]),
            {
                'salaire_base': '600000', 'jours_chomes': '2',
                'prime_performance': '0', 'prime_exceptionnelle': '0',
                'deductions': '0', 'observations': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        etat.refresh_from_db()
        self.assertEqual(etat.retenue_jours_chomes, Decimal('60000'))
        self.assertEqual(etat.jours_travailles, 19)  # 21 jours ouvrables en mai 2026
        self.assertEqual(etat.salaire_net, Decimal('1420000'))

    def test_secondaire_paye_selon_emploi_du_temps_et_absences(self):
        prof = self.creer_prof()
        self.assertEqual(heures_emploi_du_temps(prof, self.periode), Decimal('44'))

        etat, _ = calculer_etat_salaire(prof, self.periode, self.user)
        self.assertEqual(etat.source_heures, SourceHeuresSalaire.EMPLOI_DU_TEMPS)
        self.assertEqual(etat.heures_a_prester, Decimal('44'))
        self.assertEqual(etat.salaire_base, Decimal('594000'))

        response = self.client.post(
            reverse('salaires:variables_paie_periode', args=[self.periode.pk]),
            {
                f'jours_chomes_{etat.pk}': '0',
                f'prime_performance_{etat.pk}': '',
                f'prime_exceptionnelle_{etat.pk}': '25000',
                f'heures_absence_{etat.pk}': '2',
                f'heures_revision_{etat.pk}': '12',
                f'classes_professeur_principal_{etat.pk}': '1',
            },
        )
        self.assertEqual(response.status_code, 302)
        etat.refresh_from_db()
        self.assertEqual(etat.total_heures, Decimal('42'))
        self.assertEqual(etat.salaire_base, Decimal('567000'))
        self.assertEqual(etat.prime_professeur_principal, Decimal('50000'))
        self.assertEqual(etat.prime_revision, Decimal('120000'))
        self.assertEqual(etat.primes, Decimal('195000'))
        self.assertEqual(etat.salaire_net, Decimal('762000'))

    def test_saisie_mensuelle_reste_prioritaire_sur_emploi_du_temps(self):
        prof = self.creer_prof()
        etat, _ = calculer_etat_salaire(prof, self.periode, self.user)
        self.client.post(
            reverse('salaires:ajuster_etat_salaire', args=[etat.pk]),
            {
                'total_heures': '30', 'taux_horaire_applique': '13500',
                'jours_chomes': '0', 'deductions': '0', 'observations': '',
            },
        )
        etat.refresh_from_db()
        self.assertEqual(etat.source_heures, SourceHeuresSalaire.SAISIE_MENSUELLE)
        self.assertEqual(etat.total_heures, Decimal('30'))

    def test_bareme_vide_ne_change_pas_la_paie(self):
        ParametresPaie.objects.filter(ecole=self.ecole).delete()
        dg = self.creer_dg()
        etat, _ = calculer_etat_salaire(dg, self.periode, self.user)
        self.assertEqual(etat.prime_anciennete, 0)
        self.assertEqual(etat.prime_eloignement, 0)
        self.assertEqual(etat.salaire_net, Decimal('1400000'))

    def test_page_bareme_enregistre_les_montants(self):
        response = self.client.post(reverse('salaires:parametres_paie'), {
            'prime_anciennete_par_an': '12000',
            'prime_eloignement_par_km': '2000',
            'retenue_par_jour_chome': '0',
            'prime_professeur_principal': '50000',
            'prime_heure_revision': '10000',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ParametresPaie.objects.get(ecole=self.ecole).prime_anciennete_par_an,
            Decimal('12000'),
        )

    def test_documents_de_paie_pdf(self):
        dg = self.creer_dg()
        prof = self.creer_prof()
        calculer_etat_salaire(dg, self.periode, self.user)
        calculer_etat_salaire(prof, self.periode, self.user)

        page = self.client.get(reverse('salaires:documents_periode', args=[self.periode.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Direction')
        self.assertContains(page, 'Secondaire')

        etat_pdf = self.client.get(reverse('salaires:pdf_etat_salaire', args=[self.periode.pk]))
        self.assertEqual(etat_pdf.status_code, 200)
        texte = texte_pdf(etat_pdf)
        self.assertIn('Hamed BAMBA', texte)
        self.assertIn('1 480 000', texte)  # brut du DG sans primes du mois
        self.assertIn('Kadiatou DIALLO', texte)
        self.assertIn('594 000', texte)

        secondaire = self.client.get(
            reverse('salaires:pdf_etat_salaire', args=[self.periode.pk]),
            {'categorie': 'SECONDAIRE'},
        )
        self.assertNotIn('Hamed BAMBA', texte_pdf(secondaire))

        masse = texte_pdf(self.client.get(
            reverse('salaires:pdf_masse_salariale', args=[self.periode.pk])
        ))
        self.assertIn('MASSE SALARIALE', masse)
        self.assertIn('2 074 000', masse)

        emargement = texte_pdf(self.client.get(
            reverse('salaires:pdf_emargement', args=[self.periode.pk])
        ))
        self.assertIn('POUR ACQUIS', emargement)
        self.assertIn('0408219', emargement)

        bulletin = texte_pdf(self.client.get(
            reverse('salaires:fiche_paie_pdf', args=[dg.etats_salaire.get().pk])
        ))
        self.assertIn('Prime de fonction', bulletin)
        self.assertIn("Prime d'éloignement", bulletin)
        self.assertIn('Matricule: 0499120', bulletin)

        self.assertEqual(self.client.get(
            reverse('salaires:pdf_etat_salaire', args=[self.periode.pk]),
            {'categorie': 'INCONNUE'},
        ).status_code, 404)

    def test_documents_interdits_a_une_autre_ecole(self):
        autre = Ecole.objects.create(
            nom='Autre', adresse='Siguiri', telephone='620000003',
            directeur='Direction', etat='VALIDE',
        )
        periode = PeriodeSalaire.objects.create(
            ecole=autre, mois=5, annee=2026, cree_par=self.user,
        )
        utilisateur = get_user_model().objects.create_user('comptable', password='x')
        utilisateur.profil.ecole = self.ecole
        utilisateur.profil.save()
        self.client.force_login(utilisateur)
        response = self.client.get(reverse('salaires:pdf_masse_salariale', args=[periode.pk]))
        self.assertEqual(response.status_code, 404)

    def test_montants_en_lettres(self):
        self.assertEqual(
            montant_en_lettres(Decimal('6565000')),
            'Six millions cinq cent soixante-cinq mille francs guinéens',
        )
        self.assertEqual(
            montant_en_lettres(20917500),
            'Vingt millions neuf cent dix-sept mille cinq cents francs guinéens',
        )
        self.assertEqual(nombre_en_lettres(71), 'soixante et onze')
        self.assertEqual(nombre_en_lettres(80), 'quatre-vingts')
        self.assertEqual(nombre_en_lettres(280000), 'deux cent quatre-vingt mille')
        self.assertEqual(nombre_en_lettres(1000), 'mille')
        self.assertEqual(nombre_en_lettres(200), 'deux cents')
