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
        self.assertEqual(historique.donnees_avant['montant'], '100000')
        self.assertEqual(historique.donnees_apres['montant'], '200000')
        self.assertIn('montant', historique.champs_modifies)
        self.assertIn('Montant incomplet', historique.motif)
        self.eleve.echeancier.refresh_from_db()
        self.assertEqual(self.eleve.echeancier.tranche_1_payee, Decimal('200000'))

        detail = self.client.get(reverse('paiements:detail_paiement', args=[self.paiement.id]))
        self.assertContains(detail, 'Mémoire des modifications')
        self.assertContains(detail, 'Montant incomplet')

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
