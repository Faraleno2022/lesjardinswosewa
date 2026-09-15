"""Régressions : conserver les remises de tranche entre plusieurs versements."""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve
from paiements.models import (
    EcheancierPaiement, ModePaiement, Paiement, PaiementRemise,
    RemiseReduction, TypePaiement,
)
from paiements.services import calculer_situation_echeancier
from paiements.tests.support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RemisesVersementsSuccessifsTests(TestCase):
    def setUp(self):
        ecole = Ecole.objects.create(
            nom='Remises successives', adresse='Conakry',
            telephone='+224600000051', directeur='Direction', etat='VALIDE',
        )
        classe = Classe.objects.create(
            ecole=ecole, nom='6eme A', niveau='COLLEGE_6',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='REMISES-001', nom='Bah', prenom='Aminata', sexe='F',
            classe=classe,
        )
        self.type = TypePaiement.objects.create(nom='Scolarité', categorie='SCOLARITE')
        self.mode = ModePaiement.objects.create(nom='Espèces')
        self.ech = EcheancierPaiement.objects.create(
            eleve=self.eleve, annee_scolaire='2026-2027',
            frais_inscription_du=0, tranche_1_due=500000,
            tranche_2_due=300000, tranche_3_due=200000,
            date_echeance_inscription=date.today(),
            date_echeance_tranche_1=date.today() + timedelta(days=30),
            date_echeance_tranche_2=date.today() + timedelta(days=60),
            date_echeance_tranche_3=date.today() + timedelta(days=90),
        )
        self.premier = self.payer(450000)
        remise = RemiseReduction.objects.create(
            nom='Bourse T1', type_remise='MONTANT_FIXE', valeur=50000,
            motif='SOCIALE', date_debut=date.today(),
            date_fin=date.today() + timedelta(days=365),
        )
        self.remise = PaiementRemise.objects.create(
            paiement=self.premier, remise=remise, montant_remise=50000,
            tranches_concernees='1', deduite_du_paiement=True,
        )

    def payer(self, montant):
        return Paiement.objects.create(
            eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=montant, date_paiement=date.today(),
            annee_scolaire='2026-2027', statut='VALIDE',
        )

    def verifier_situation(self, encaisse, remises, reste):
        self.ech.refresh_from_db()
        self.assertEqual(self.ech.total_paye, Decimal(encaisse))
        self.assertEqual(self.ech.total_remises_valides, Decimal(remises))
        self.assertEqual(self.ech.solde_restant, Decimal(reste))
        situation = calculer_situation_echeancier(self.ech)
        self.assertEqual(situation['encaisse'], Decimal(encaisse))
        self.assertEqual(situation['remises'], Decimal(remises))
        self.assertEqual(situation['reste'], Decimal(reste))

    def test_remise_premiere_tranche_survit_aux_versements_suivants(self):
        self.payer(300000)
        self.payer(200000)
        self.verifier_situation(950000, 50000, 0)
        self.assertEqual(self.ech.statut, 'PAYE_COMPLET')
        self.assertEqual(self.ech.tranche_1_payee, 450000)
        self.assertEqual(self.ech.tranche_2_payee, 300000)
        self.assertEqual(self.ech.tranche_3_payee, 200000)

    def test_modifier_supprimer_et_restaurer_recalcule_sans_perdre_la_remise(self):
        second = self.payer(300000)
        self.payer(200000)
        second.montant = 250000
        second.save()
        self.verifier_situation(900000, 50000, 50000)
        self.premier.statut = 'ANNULE'
        self.premier.save()
        self.verifier_situation(450000, 0, 550000)
        self.premier.statut = 'VALIDE'
        self.premier.save()
        self.verifier_situation(900000, 50000, 50000)
        second.delete()
        self.verifier_situation(650000, 50000, 300000)
        self.premier.refresh_from_db()
        self.remise.refresh_from_db()
        self.assertEqual(self.premier.montant, 450000)
        self.assertEqual(self.remise.montant_remise, 50000)

    def connecter(self):
        user = User.objects.create_superuser('recalcul-remises', 'test@example.test', 'secret')
        self.client.force_login(user)
        return user

    def test_fiche_et_carnet_annoncent_le_meme_solde_et_la_bonne_echeance(self):
        from paiements.carnet_paiement import collecter_carnet_paiement
        self.connecter()
        second = self.payer(250000)
        self.payer(200000)
        response = self.client.get(reverse('paiements:echeancier_eleve', args=[self.eleve.pk]))
        self.assertEqual(response.status_code, 200)
        situation = response.context['finance_eleve']
        self.assertEqual(situation['reste_a_payer'], 50000)
        self.assertEqual(situation['remises_total'], 50000)
        self.assertEqual(situation['prochain_paiement']['code'], 'TRANCHE_3')
        self.assertEqual(situation['prochain_paiement']['reste'], 50000)
        carnet = collecter_carnet_paiement(second)
        self.assertEqual(carnet['reste_final'], 50000)
        self.assertEqual(carnet['total_encaisse'], 900000)
        self.assertEqual(carnet['total_remises'], 50000)

    def test_remise_sur_prochain_recu_exclut_la_tranche_deja_soldee(self):
        self.connecter()
        paiement = self.payer(300000)
        paiement.statut = 'EN_ATTENTE'
        paiement.save()
        response = self.client.get(reverse('paiements:appliquer_remise', args=[paiement.pk]))
        self.assertEqual(response.status_code, 200)
        tranches = {t['numero']: t for t in response.context['tranches_info']}
        self.assertEqual(tranches[1]['du'], 0)
        self.assertEqual(tranches[1]['sur_ce_paiement'], 0)
        self.assertEqual(tranches[2]['sur_ce_paiement'], 300000)

    def test_remise_sur_paiement_reappliquee_conserve_sa_base_brute(self):
        self.connecter()
        paiement = self.payer(300000)
        paiement.statut = 'EN_ATTENTE'
        paiement.save()
        url = reverse('paiements:appliquer_remise', args=[paiement.pk])
        donnees = {
            'montant_original': '300000',
            'pourcentage_scolarite': '10', 'tranches': ['2'],
            'motif': 'GESTE_COMMERCIAL', 'base_calcul': 'PAIEMENT_ECHEANCE',
            'reduire_paiement': '1',
        }
        for _ in range(2):
            response = self.client.post(url, donnees)
            self.assertEqual(response.status_code, 302)
            paiement.refresh_from_db()
            self.assertEqual(paiement.montant, 270000)
            self.assertEqual(paiement.remises.get().montant_remise, 30000)

    def test_ancien_tarif_depasse_preserve_le_cash_et_plafonne_la_remise(self):
        from paiements.views import _auto_validate_echeancier_for_eleve
        self.payer(300000)
        self.payer(200000)
        self.ech.tranche_3_due = 160000
        self.ech.save()
        _auto_validate_echeancier_for_eleve(
            self.eleve, preserve_recorded=False, annee_scolaire='2026-2027', strict=True,
        )
        self.verifier_situation(950000, 10000, 0)
        self.ech.tranche_3_due = 140000
        self.ech.save()
        _auto_validate_echeancier_for_eleve(
            self.eleve, preserve_recorded=False, annee_scolaire='2026-2027', strict=True,
        )
        self.verifier_situation(940000, 0, 0)
        self.assertEqual(sum(Paiement.objects.values_list('montant', flat=True)), 950000)

    def test_recu_pdf_et_ventilation_deduisent_la_remise_de_la_bonne_tranche(self):
        import re
        from io import BytesIO
        from pypdf import PdfReader
        from paiements.allocation import build_payment_allocation_history
        self.connecter()
        second = self.payer(250000)
        dernier = self.payer(200000)
        response = self.client.get(reverse('paiements:generer_recu_pdf', args=[dernier.pk]))
        self.assertEqual(response.status_code, 200)
        texte = ''.join(page.extract_text() for page in PdfReader(BytesIO(response.content)).pages)
        compact = re.sub(r'\s+', '', texte)
        self.assertIn('Soldeglobalrestant:50000GNF', compact)
        restes = compact.split('Restesàpayerpartranche')[1]
        self.assertIn('1èretranche:0GNF', restes)
        self.assertIn('2èmetranche:0GNF', restes)
        self.assertIn('3èmetranche:50000GNF', restes)
        allocations, restants = build_payment_allocation_history(
            self.ech, [self.premier, second, dernier],
        )
        self.assertEqual(allocations[second.pk]['tranche_1'], 0)
        self.assertEqual(allocations[second.pk]['tranche_2'], 250000)
        self.assertEqual(sum(restants.values()), 50000)
