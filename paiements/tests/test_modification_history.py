import re
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve
from paiements.models import (
    EcheancierPaiement, HistoriqueModificationPaiement,
    ModePaiement, Paiement, TypePaiement,
)
from paiements.tests.support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ModificationPaiementHistoriqueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin-paiement-edit', 'edit@test.local', 'secret')
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(
            nom='École Paiement Edit', adresse='Conakry', telephone='+224622000201',
            directeur='Direction', etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='7ème A', niveau='COLLEGE_7',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='EDIT-001', prenom='Mamadou', nom='Bah', sexe='M',
            classe=self.classe,
        )
        self.type = TypePaiement.objects.create(nom='Scolarité edit')
        self.mode = ModePaiement.objects.create(nom='Espèces edit')
        self.paiement = Paiement.objects.create(
            eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=Decimal('100000'), date_paiement=date.today(), statut='VALIDE',
        )
        EcheancierPaiement.objects.create(
            eleve=self.eleve, annee_scolaire='2026-2027',
            frais_inscription_du=0, tranche_1_due=500000,
            tranche_2_due=0, tranche_3_due=0,
            frais_inscription_paye=0, tranche_1_payee=100000,
            tranche_2_payee=0, tranche_3_payee=0,
            date_echeance_inscription=date.today() - timedelta(days=1),
            date_echeance_tranche_1=date.today() + timedelta(days=30),
            date_echeance_tranche_2=date.today() + timedelta(days=60),
            date_echeance_tranche_3=date.today() + timedelta(days=90),
        )

    def test_modification_conserve_avant_apres_auteur_et_recalcule(self):
        response = self.client.post(
            reverse('paiements:modifier_paiement', args=[self.paiement.id]),
            {
                'type_paiement': self.type.id,
                'mode_paiement': self.mode.id,
                'montant': '200000',
                'date_paiement': date.today().isoformat(),
                'reference_externe': 'CORR-001',
                'observations': 'Montant complété',
                'motif_modification': 'Montant incomplet lors de la saisie initiale',
            },
        )
        self.assertRedirects(
            response, reverse('paiements:detail_paiement', args=[self.paiement.id])
        )
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('200000'))
        historique = HistoriqueModificationPaiement.objects.get(paiement=self.paiement)
        self.assertEqual(historique.utilisateur, self.user)
        self.assertEqual(historique.ecole, self.ecole)
        self.assertEqual(
            historique.operation,
            HistoriqueModificationPaiement.Operation.MODIFICATION,
        )
        self.assertEqual(historique.donnees_avant['montant'], '100000')
        self.assertEqual(historique.donnees_apres['montant'], '200000')
        self.assertIn('montant', historique.champs_modifies)
        self.assertIn('Montant incomplet', historique.motif)
        self.eleve.echeancier.refresh_from_db()
        self.assertEqual(self.eleve.echeancier.tranche_1_payee, Decimal('200000'))

        detail = self.client.get(reverse('paiements:detail_paiement', args=[self.paiement.id]))
        self.assertContains(detail, 'Mémoire des modifications')
        self.assertContains(detail, 'Montant incomplet')

        dashboard = self.client.get(reverse('paiements:tableau_bord'))
        periode_jour = {
            item['key']: item for item in dashboard.context['audit_paiements']
        }['jour']
        self.assertEqual(periode_jour['modifications'], 1)
        self.assertEqual(periode_jour['montant_avant'], Decimal('100000'))
        self.assertEqual(periode_jour['montant_apres'], Decimal('200000'))
        self.assertEqual(periode_jour['variation_nette'], Decimal('100000'))

    def test_suppression_douce_garde_motif_et_recalcule_toutes_les_cartes(self):
        response = self.client.post(
            reverse('paiements:supprimer_paiement', args=[self.paiement.id]),
            {'motif_suppression': 'Reçu créé en double par erreur'},
        )
        self.assertRedirects(
            response,
            reverse('paiements:detail_paiement', args=[self.paiement.id]),
        )
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'ANNULE')
        self.assertEqual(
            self.paiement.motif_annulation,
            'Reçu créé en double par erreur',
        )
        historique = HistoriqueModificationPaiement.objects.get(
            paiement=self.paiement,
            operation=HistoriqueModificationPaiement.Operation.SUPPRESSION,
        )
        self.assertEqual(historique.montant_avant, Decimal('100000'))
        self.assertEqual(historique.motif, 'Reçu créé en double par erreur')

        self.eleve.echeancier.refresh_from_db()
        self.assertEqual(self.eleve.echeancier.tranche_1_payee, Decimal('0'))

        dashboard = self.client.get(reverse('paiements:tableau_bord'))
        periode_jour = {
            item['key']: item for item in dashboard.context['audit_paiements']
        }['jour']
        self.assertEqual(periode_jour['suppressions'], 1)
        self.assertEqual(periode_jour['montant_supprime'], Decimal('100000'))
        categories = {
            item['key']: item for item in dashboard.context['indicateurs_categories']
        }
        scolarite_jour = {
            item['key']: item for item in categories['scolarite']['periodes']
        }['jour']
        self.assertEqual(scolarite_jour['montant'], Decimal('0'))

        journal = self.client.get(reverse('paiements:historique_operations'))
        self.assertContains(journal, 'Reçu créé en double par erreur')
        self.assertContains(journal, 'Suppression douce')

    def test_suppression_refusee_sans_motif(self):
        response = self.client.post(
            reverse('paiements:supprimer_paiement', args=[self.paiement.id]),
            {'motif_suppression': ''},
        )
        self.assertEqual(response.status_code, 200)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.statut, 'VALIDE')
        self.assertFalse(
            HistoriqueModificationPaiement.objects.filter(
                operation=HistoriqueModificationPaiement.Operation.SUPPRESSION,
            ).exists()
        )

    def test_annulation_synchronisee_est_reconnue_comme_suppression(self):
        """Le poste destinataire n'a pas les attributs temporaires de la vue."""
        self.paiement.statut = 'ANNULE'
        self.paiement.motif_annulation = 'Annulation reçue du poste principal'
        self.paiement.save(update_fields=[
            'statut', 'motif_annulation', 'date_modification',
        ])

        historique = HistoriqueModificationPaiement.objects.get(
            paiement=self.paiement,
        )
        self.assertEqual(
            historique.operation,
            HistoriqueModificationPaiement.Operation.SUPPRESSION,
        )
        self.assertEqual(
            historique.motif,
            'Annulation reçue du poste principal',
        )

    def test_le_champ_montant_accepte_les_montants_ronds(self):
        """Le couple min/step du champ ne doit refuser aucun montant entier.

        Avec min=1 et step=1000, le navigateur n'acceptait que 1, 1001,
        2001... : la page refusait 200 000 GNF, et même le montant déjà
        enregistré, avant tout envoi au serveur.
        """
        response = self.client.get(
            reverse('paiements:modifier_paiement', args=[self.paiement.id])
        )
        self.assertEqual(response.status_code, 200)
        champ = re.search(
            r'<input[^>]*name="montant"[^>]*>', response.content.decode()
        )
        self.assertIsNotNone(champ, "Le champ montant doit être rendu.")
        balise = champ.group(0)
        minimum = Decimal(re.search(r'min="([^"]+)"', balise).group(1))
        pas = Decimal(re.search(r'step="([^"]+)"', balise).group(1))
        for montant in (Decimal('200000'), Decimal('250000'), self.paiement.montant):
            self.assertEqual(
                (montant - minimum) % pas, Decimal('0'),
                f"{montant} GNF serait refusé par le navigateur "
                f"(min={minimum}, step={pas}).",
            )

    def test_motif_est_obligatoire(self):
        response = self.client.post(
            reverse('paiements:modifier_paiement', args=[self.paiement.id]),
            {
                'type_paiement': self.type.id,
                'mode_paiement': self.mode.id,
                'montant': '200000',
                'date_paiement': date.today().isoformat(),
                'motif_modification': '',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ce champ est obligatoire')
        self.assertFalse(HistoriqueModificationPaiement.objects.exists())


    def _admission_avec_remise(self, nature, montant):
        from eleves.models import GrilleTarifaire
        from paiements.models import PaiementRemise, RemiseReduction
        GrilleTarifaire.objects.create(
            ecole=self.ecole, niveau=self.classe.niveau,
            annee_scolaire=self.classe.annee_scolaire,
            frais_inscription=50000, frais_reinscription=30000,
            tranche_1=500000, tranche_2=0, tranche_3=0,
        )
        self.inscription = TypePaiement.objects.create(nom='Inscription + Tranche 1')
        self.reinscription = TypePaiement.objects.create(nom='Réinscription + Tranche 1')
        self.paiement.type_paiement = getattr(self, nature)
        self.paiement.montant = Decimal(montant)
        self.paiement.save()
        remise = RemiseReduction.objects.create(
            nom='Remise 10 % T1', type_remise='POURCENTAGE', valeur=10,
            motif='SOCIALE', date_debut=date.today(),
            date_fin=date.today() + timedelta(days=365),
        )
        self.remise_appliquee = PaiementRemise.objects.create(
            paiement=self.paiement, remise=remise, montant_remise=50000,
            tranches_concernees='1', base_calcul='TRANCHES_DUES',
            deduite_du_paiement=True,
        )

    def _corriger_admission(self, type_paiement, montant):
        return self.client.post(
            reverse('paiements:modifier_paiement', args=[self.paiement.pk]),
            {
                'type_paiement': type_paiement.pk, 'mode_paiement': self.mode.pk,
                'montant': str(montant), 'date_paiement': date.today().isoformat(),
                'motif_modification': 'Correction du type admission choisi par erreur',
            },
        )

    def test_correction_vers_inscription_utilise_nouveau_plafond_avec_remise(self):
        self._admission_avec_remise('reinscription', '480000')
        response = self._corriger_admission(self.inscription, 500000)
        self.assertEqual(response.status_code, 302)
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.nature_frais, 'INSCRIPTION')
        self.assertEqual(ech.total_du, Decimal('550000'))
        self.assertEqual(ech.total_paye, Decimal('500000'))
        self.assertEqual(ech.total_remises_valides, Decimal('50000'))
        self.assertEqual(ech.solde_restant, 0)
        self.assertEqual(ech.statut, 'PAYE_COMPLET')

    def test_correction_vers_reinscription_refuse_depassement_sans_effet(self):
        self._admission_avec_remise('inscription', '500000')
        response = self._corriger_admission(self.reinscription, 510000)
        self.assertEqual(response.status_code, 200)
        self.assertIn('montant', response.context['form'].errors)
        self.paiement.refresh_from_db()
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(self.paiement.type_paiement, self.inscription)
        self.assertEqual(ech.nature_frais, 'INSCRIPTION')
        self.assertEqual(ech.frais_inscription_du, Decimal('50000'))

    def test_correction_reinscription_remise_cartes_recu_et_annulation(self):
        from io import BytesIO
        from pypdf import PdfReader
        from paiements.services import calculer_situation_echeancier
        self._admission_avec_remise('inscription', '500000')
        response = self._corriger_admission(self.reinscription, 500000)
        self.assertEqual(response.status_code, 302)
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.nature_frais, 'REINSCRIPTION')
        self.assertEqual(ech.frais_inscription_du, Decimal('30000'))
        self.assertEqual(ech.total_paye, Decimal('480000'))
        self.assertEqual(ech.total_remises_valides, Decimal('50000'))
        self.assertEqual(ech.solde_restant, 0)
        situation = calculer_situation_echeancier(ech)
        self.assertEqual(situation['total_du'], Decimal('530000'))
        self.assertEqual(situation['reste'], 0)
        self.remise_appliquee.refresh_from_db()
        self.assertEqual(self.remise_appliquee.montant_remise, Decimal('50000'))
        self.assertTrue(self.remise_appliquee.deduite_du_paiement)
        dashboard = self.client.get(reverse('paiements:tableau_bord'))
        categories = {x['key']: x for x in dashboard.context['indicateurs_categories']}
        jour = {x['key']: x for x in categories['scolarite']['periodes']}['jour']
        self.assertEqual(jour['montant'], Decimal('450000'))
        admission = {x['key']: x for x in categories['reinscription']['periodes']}['jour']
        self.assertEqual(admission['montant'], Decimal('30000'))
        inscription = {x['key']: x for x in categories['inscription']['periodes']}['jour']
        self.assertEqual(inscription['montant'], 0)
        pdf = self.client.get(reverse('paiements:generer_recu_pdf', args=[self.paiement.pk]))
        self.assertEqual(pdf.status_code, 200)
        texte = ''.join(page.extract_text() for page in PdfReader(BytesIO(pdf.content)).pages)
        self.assertIn('Réinscription', texte)
        for montant in ('480000', '50000', '530000'):
            self.assertIn(montant, re.sub(r'[,\s\u00a0\u202f]', '', texte))
        self.client.post(
            reverse('paiements:supprimer_paiement', args=[self.paiement.pk]),
            {'motif_suppression': 'Annulation du reçu corrigé'},
        )
        ech.refresh_from_db()
        self.assertEqual(ech.total_paye, 0)
        self.assertEqual(ech.total_remises_valides, 0)
        self.assertEqual(ech.solde_restant, Decimal('530000'))
        dashboard = self.client.get(reverse('paiements:tableau_bord'))
        categories = {x['key']: x for x in dashboard.context['indicateurs_categories']}
        jour = {x['key']: x for x in categories['scolarite']['periodes']}['jour']
        self.assertEqual(jour['montant'], 0)


    def test_correction_partielle_recalcule_solde_sans_deduire_remise_deux_fois(self):
        self._admission_avec_remise('inscription', '200000')
        response = self._corriger_admission(self.reinscription, 190000)
        self.assertEqual(response.status_code, 302)
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.total_du, Decimal('530000'))
        self.assertEqual(ech.total_paye, Decimal('190000'))
        self.assertEqual(ech.total_remises_valides, Decimal('50000'))
        self.assertEqual(ech.solde_restant, Decimal('290000'))

    def test_controle_transactionnel_utilise_aussi_le_nouveau_tarif(self):
        from django.core.exceptions import ValidationError
        from paiements.views import _assert_payment_fits_annual_balance
        self._admission_avec_remise('inscription', '500000')
        self.paiement.type_paiement = self.reinscription
        with self.assertRaises(ValidationError):
            _assert_payment_fits_annual_balance(self.paiement)
        self.paiement.montant = Decimal('480000')
        projection = _assert_payment_fits_annual_balance(self.paiement)
        self.assertEqual(projection.total_du, Decimal('530000'))
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.total_du, Decimal('550000'))

    def test_api_statistiques_reflete_correction_et_annulation(self):
        self._admission_avec_remise('inscription', '200000')
        self._corriger_admission(self.reinscription, 180000)
        url = reverse('paiements:ajax_statistiques_paiements')
        response = self.client.get(url)
        self.assertEqual(response.json()['stats']['total_paiements_mois'], 180000)
        self.client.post(
            reverse('paiements:supprimer_paiement', args=[self.paiement.pk]),
            {'motif_suppression': 'Annulation du paiement de test'},
        )
        self.assertEqual(self.client.get(url).json()['stats']['total_paiements_mois'], 0)

    def test_changement_type_seul_recalcule_net_sans_deduire_remise_deux_fois(self):
        self._admission_avec_remise('inscription', '500000')
        response = self._corriger_admission(self.reinscription, 500000)
        self.assertEqual(response.status_code, 302)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('480000'))
        self.remise_appliquee.refresh_from_db()
        self.assertEqual(self.remise_appliquee.montant_remise, Decimal('50000'))
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.total_du, Decimal('530000'))
        self.assertEqual(ech.solde_restant, 0)
        # Sauvegarder une seconde fois ne doit pas rejouer la différence.
        response = self._corriger_admission(self.reinscription, 480000)
        self.assertEqual(response.status_code, 302)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('480000'))
        # Le retour vers inscription doit également être automatique.
        response = self._corriger_admission(self.inscription, 480000)
        self.assertEqual(response.status_code, 302)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('500000'))
        ech.refresh_from_db()
        self.assertEqual(ech.total_du, Decimal('550000'))
        self.assertEqual(ech.solde_restant, 0)

    def test_correction_automatique_sans_remise(self):
        self._admission_avec_remise('inscription', '500000')
        self.remise_appliquee.delete()
        response = self._corriger_admission(self.reinscription, 500000)
        self.assertEqual(response.status_code, 302)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('480000'))
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.solde_restant, Decimal('50000'))

    def test_correction_automatique_non_positive_refusee_sans_ecriture(self):
        self._admission_avec_remise('inscription', '10000')
        response = self._corriger_admission(self.reinscription, 10000)
        self.assertEqual(response.status_code, 200)
        self.assertIn('montant', response.context['form'].errors)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('10000'))
        self.assertEqual(self.paiement.type_paiement, self.inscription)
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.nature_frais, 'INSCRIPTION')

    def test_changement_de_tranche_ne_devine_pas_le_montant(self):
        self._admission_avec_remise('inscription', '100000')
        autre_type = TypePaiement.objects.create(nom='Réinscription + Tranche 2')
        response = self._corriger_admission(autre_type, 100000)
        self.assertEqual(response.status_code, 302)
        self.paiement.refresh_from_db()
        self.assertEqual(self.paiement.montant, Decimal('100000'))
