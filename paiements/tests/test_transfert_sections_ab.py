from datetime import date
from decimal import Decimal
from io import BytesIO
import re

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire
from paiements.models import EcheancierPaiement, Paiement, PaiementRemise, ModePaiement, RemiseReduction, TypePaiement
from paiements.services import calculer_situation_echeancier
from paiements.views import ensure_echeancier_for_eleve
from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TransfertSectionsABTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('transfert-ab', 'test@example.com', 'test')
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(nom='École A B', adresse='Conakry', telephone='620000010', directeur='Direction', etat='VALIDE')
        self.a = Classe.objects.create(ecole=self.ecole, nom='Petite section A', niveau='PETITE_SECTION', annee_scolaire='2026-2027')
        self.b = Classe.objects.create(ecole=self.ecole, nom='Petite section B', niveau='PETITE_SECTION', annee_scolaire='2026-2027')
        GrilleTarifaire.objects.create(ecole=self.ecole, niveau=self.a.niveau, annee_scolaire=self.a.annee_scolaire,
            frais_inscription=50000, frais_reinscription=30000, tranche_1=500000, tranche_2=300000, tranche_3=200000)
        self.eleve = Eleve.objects.create(nom='Diallo', prenom='Aminata', sexe='F', matricule='AB-001', classe=self.a)
        ensure_echeancier_for_eleve(self.eleve, annee_scolaire='2026-2027')
        self.type = TypePaiement.objects.create(nom='Scolarité', categorie='SCOLARITE')
        self.mode = ModePaiement.objects.create(nom='Espèces A B')
        self.premier = self.payer(500000)
        remise = RemiseReduction.objects.create(nom='Remise T1', type_remise='POURCENTAGE', valeur=10,
            motif='SOCIALE', date_debut=date(2026, 9, 1), date_fin=date(2027, 8, 31))
        self.remise = PaiementRemise.objects.create(paiement=self.premier, remise=remise, montant_remise=50000,
            tranches_concernees='1', base_calcul='TRANCHES_DUES', deduite_du_paiement=True)
        self.second = self.payer(250000)
        self.dernier = self.payer(200000)

    def payer(self, montant):
        return Paiement.objects.create(eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=montant, statut='VALIDE', annee_scolaire='2026-2027', date_paiement=date.today())

    def transferer(self):
        response = self.client.post(reverse('eleves:repartir_eleves'), {
            'eleve_id': self.eleve.pk, 'ancienne_classe_id': self.eleve.classe_id,
            'classe_id': self.b.pk, 'action': 'enregistrer',
        })
        self.assertEqual(response.status_code, 302)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.classe_id, self.b.pk)

    def test_a_vers_b_conserve_remise_versements_solde_et_recu(self):
        self.transferer()
        ech = EcheancierPaiement.objects.get(eleve=self.eleve, annee_scolaire='2026-2027')
        self.assertEqual(ech.total_du, 1050000)
        self.assertEqual(ech.total_paye, 950000)
        self.assertEqual(ech.total_remises_valides, 50000)
        self.assertEqual(ech.solde_restant, 50000)
        self.assertEqual(ech.tranche_1_payee, 450000)
        self.assertEqual(ech.tranche_2_payee, 300000)
        self.assertEqual(ech.tranche_3_payee, 150000)
        self.assertEqual(self.eleve.echeanciers.count(), 1)
        for paiement, montant in ((self.premier, 500000), (self.second, 250000), (self.dernier, 200000)):
            paiement.refresh_from_db()
            self.assertEqual(paiement.montant, montant)
            self.assertEqual(paiement.classe_encaissement_id, self.a.pk)
        self.remise.refresh_from_db()
        self.assertEqual(self.remise.montant_remise, 50000)
        self.assertTrue(self.remise.deduite_du_paiement)
        situation = calculer_situation_echeancier(ech)
        self.assertEqual(situation['reste'], 50000)
        response = self.client.get(reverse('paiements:echeancier_eleve', args=[self.eleve.pk]))
        self.assertEqual(response.context['finance_eleve']['reste_a_payer'], 50000)
        pdf = self.client.get(reverse('paiements:generer_recu_pdf', args=[self.dernier.pk]))
        self.assertEqual(pdf.status_code, 200)
        texte = ''.join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
        self.assertIn('Soldeglobalrestant:50000GNF', re.sub(r'\s+', '', texte))

    def test_recapitulatif_par_classe_ne_multiplie_pas_le_du_par_les_versements(self):
        self.transferer()
        response = self.client.get(reverse('paiements:liste_paiements'), {'annee': '2026-2027'})
        self.assertEqual(response.status_code, 200)
        lignes = response.context['totaux_du_detail_classes']
        self.assertEqual(len(lignes), 1)
        self.assertEqual(lignes[0]['classe_id'], self.b.pk)
        self.assertEqual(lignes[0]['eleves_count'], 1)
        self.assertEqual(lignes[0]['du_global_net'], 1000000)
        self.assertEqual(response.context['totaux_du']['du_global_net'], 1000000)

    def test_recapitulatif_compte_deux_eleves_aux_memes_tarifs_et_remises(self):
        self.transferer()
        autre = Eleve.objects.create(nom='Camara', prenom='Fatou', sexe='F', matricule='AB-002', classe=self.b)
        ensure_echeancier_for_eleve(autre, annee_scolaire='2026-2027')
        paiement = Paiement.objects.create(eleve=autre, type_paiement=self.type, mode_paiement=self.mode,
            montant=100000, statut='VALIDE', annee_scolaire='2026-2027', date_paiement=date.today())
        PaiementRemise.objects.create(paiement=paiement, remise=self.remise.remise, montant_remise=50000,
            tranches_concernees='1', base_calcul='TRANCHES_DUES', deduite_du_paiement=True)
        response = self.client.get(reverse('paiements:liste_paiements'), {'annee': '2026-2027'})
        ligne = response.context['totaux_du_detail_classes'][0]
        self.assertEqual(ligne['classe_id'], self.b.pk)
        self.assertEqual(ligne['eleves_count'], 2)
        self.assertEqual(ligne['du_global_net'], 2000000)
        self.assertEqual(ligne['frais_inscription_total'], 100000)
        self.assertEqual(response.context['totaux_du']['du_global_net'], 2000000)

    def test_modification_et_annulation_apres_transfert(self):
        self.transferer()
        self.dernier.montant = Decimal('150000')
        self.dernier.save()
        ech = EcheancierPaiement.objects.get(eleve=self.eleve)
        self.assertEqual(ech.solde_restant, 100000)
        self.second.statut = 'ANNULE'
        self.second.save()
        ech.refresh_from_db()
        self.assertEqual(ech.total_paye, 650000)
        self.assertEqual(ech.total_remises_valides, 50000)
        self.assertEqual(ech.solde_restant, 350000)
        self.second.statut = 'VALIDE'
        self.second.save()
        ech.refresh_from_db()
        self.assertEqual(ech.total_paye, 900000)
        self.assertEqual(ech.solde_restant, 100000)
