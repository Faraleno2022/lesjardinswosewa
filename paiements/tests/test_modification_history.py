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
