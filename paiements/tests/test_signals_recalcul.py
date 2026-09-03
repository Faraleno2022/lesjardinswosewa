"""
Recalcul de l'echeancier apres suppression ou modification d'un paiement.

Le mecanisme (paiements/signals.py) n'avait aucun test dedie malgre son role
central : c'est lui qui garantit qu'un solde affiche a l'ecran reste exact
apres une correction ou une suppression, quelle que soit la porte d'entree
(vue metier, admin Django, synchronisation entre postes). Ces tests exercent
les signaux directement (save()/delete() au niveau du modele), independamment
des vues qui appellent parfois _auto_validate_echeancier_for_eleve en plus,
en double.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from eleves.models import Classe, Ecole, Eleve
from paiements.models import (
    EcheancierPaiement, ModePaiement, Paiement, PaiementRemise,
    RemiseReduction, TypePaiement,
)


class RecalculApresSuppressionEtModificationTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Recalcul', adresse='Conakry', telephone='+224600000050',
            directeur='Direction', etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='6eme A', niveau='COLLEGE_6',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='RECALC-001', nom='Sow', prenom='Fatoumata', sexe='F',
            classe=self.classe,
        )
        self.type_scolarite = TypePaiement.objects.create(
            nom='Scolarite', categorie='SCOLARITE',
        )
        self.mode = ModePaiement.objects.create(nom='Especes')
        self.echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve, annee_scolaire='2026-2027',
            frais_inscription_du=0, tranche_1_due=500000,
            tranche_2_due=300000, tranche_3_due=200000,
            date_echeance_inscription=date.today() - timedelta(days=1),
            date_echeance_tranche_1=date.today() + timedelta(days=30),
            date_echeance_tranche_2=date.today() + timedelta(days=60),
            date_echeance_tranche_3=date.today() + timedelta(days=90),
        )

    def _payer(self, montant, statut='VALIDE'):
        return Paiement.objects.create(
            eleve=self.eleve, type_paiement=self.type_scolarite, mode_paiement=self.mode,
            montant=Decimal(montant), date_paiement=date.today(),
            annee_scolaire='2026-2027', statut=statut,
        )

    def _rafraichir(self):
        self.echeancier.refresh_from_db()
        return self.echeancier

    # ── Suppression ──────────────────────────────────────────────────────────

    def test_la_suppression_d_un_paiement_reduit_le_solde_paye(self):
        premier = self._payer(100000)
        self._payer(150000)
        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('250000'))

        premier.delete()

        ech = self._rafraichir()
        self.assertEqual(
            ech.tranche_1_payee, Decimal('150000'),
            "le solde doit refleter les paiements restants, pas rester a l'ancienne valeur",
        )

    def test_la_suppression_de_tous_les_paiements_remet_le_solde_a_zero(self):
        paiement = self._payer(500000)
        ech = self._rafraichir()
        self.assertEqual(ech.statut, 'PAYE_PARTIEL')

        paiement.delete()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('0'))
        self.assertEqual(ech.tranche_2_payee, Decimal('0'))
        self.assertEqual(ech.statut, 'A_PAYER')

    def test_la_suppression_fait_repasser_le_statut_en_retard_si_echeance_depassee(self):
        """
        Une echeance de tranche_1 deja passee : sans le seul paiement qui la
        couvrait, le statut doit redevenir EN_RETARD, pas rester PAYE_PARTIEL.
        """
        self.echeancier.date_echeance_tranche_1 = date.today() - timedelta(days=1)
        self.echeancier.save()
        # Couvre le total du (T1+T2+T3 = 500000+300000+200000) pour atteindre
        # PAYE_COMPLET avant suppression, et pas seulement la tranche 1.
        paiement = self._payer(1000000)
        ech = self._rafraichir()
        self.assertEqual(ech.statut, 'PAYE_COMPLET')

        paiement.delete()

        ech = self._rafraichir()
        self.assertEqual(ech.statut, 'EN_RETARD')

    def test_un_paiement_hors_scolarite_supprime_ne_touche_pas_l_echeancier(self):
        """La cantine/le transport n'alimentent jamais l'echeancier de scolarite."""
        type_cantine = TypePaiement.objects.create(nom='Cantine', categorie='CANTINE')
        paiement_scolarite = self._payer(200000)
        paiement_cantine = Paiement.objects.create(
            eleve=self.eleve, type_paiement=type_cantine, mode_paiement=self.mode,
            montant=Decimal('50000'), date_paiement=date.today(),
            annee_scolaire='2026-2027', statut='VALIDE',
        )
        ech_avant = self._rafraichir()
        self.assertEqual(ech_avant.tranche_1_payee, Decimal('200000'))

        paiement_cantine.delete()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('200000'))
        self.assertTrue(Paiement.objects.filter(pk=paiement_scolarite.pk).exists())

    # ── Modification ─────────────────────────────────────────────────────────

    def test_augmenter_le_montant_augmente_le_solde_paye(self):
        paiement = self._payer(100000)
        paiement.montant = Decimal('300000')
        paiement.save()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('300000'))

    def test_diminuer_le_montant_diminue_le_solde_paye(self):
        paiement = self._payer(300000)
        paiement.montant = Decimal('120000')
        paiement.save()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('120000'))

    def test_faire_basculer_un_paiement_hors_statut_valide_le_retire_du_solde(self):
        """
        Rejeter un paiement (sans le supprimer) doit avoir le meme effet
        comptable qu'une suppression : il ne doit plus etre compte.
        """
        paiement = self._payer(250000)
        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('250000'))

        paiement.statut = 'REJETE'
        paiement.save()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('0'))
        self.assertEqual(ech.statut, 'A_PAYER')

    def test_reactiver_un_paiement_rejete_le_recompte(self):
        paiement = self._payer(250000, statut='REJETE')
        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('0'))

        paiement.statut = 'VALIDE'
        paiement.save()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('250000'))

    def test_changer_l_annee_scolaire_recalcule_les_deux_echeanciers(self):
        """
        pre_save memorise l'ancienne portee (eleve, annee) : un paiement
        reaffecte a une autre annee doit vider l'ancien echeancier ET remplir
        le nouveau, pas seulement l'un des deux.
        """
        autre_echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve, annee_scolaire='2027-2028',
            frais_inscription_du=0, tranche_1_due=400000,
            tranche_2_due=0, tranche_3_due=0,
            date_echeance_inscription=date.today() - timedelta(days=1),
            date_echeance_tranche_1=date.today() + timedelta(days=30),
            date_echeance_tranche_2=date.today() + timedelta(days=60),
            date_echeance_tranche_3=date.today() + timedelta(days=90),
        )
        paiement = self._payer(200000)
        self.assertEqual(self._rafraichir().tranche_1_payee, Decimal('200000'))

        paiement.annee_scolaire = '2027-2028'
        paiement.save()

        ancien = self._rafraichir()
        autre_echeancier.refresh_from_db()
        self.assertEqual(ancien.tranche_1_payee, Decimal('0'))
        self.assertEqual(autre_echeancier.tranche_1_payee, Decimal('200000'))

    # ── Remises ───────────────────────────────────────────────────────────────

    def test_la_suppression_d_une_remise_retire_sa_couverture(self):
        remise = RemiseReduction.objects.create(
            nom='Bourse', type_remise='MONTANT_FIXE', valeur=Decimal('50000'),
            motif='SOCIALE', date_debut=date.today() - timedelta(days=1),
            date_fin=date.today() + timedelta(days=365),
        )
        paiement = self._payer(200000)
        ligne_remise = PaiementRemise.objects.create(
            paiement=paiement, remise=remise, montant_remise=Decimal('50000'),
        )
        ech = self._rafraichir()
        self.assertEqual(ech.statut, 'PAYE_PARTIEL')
        # 200000 encaisses + 50000 de remise = 250000 sur 500000 dus a T1.

        ligne_remise.delete()

        ech = self._rafraichir()
        self.assertEqual(ech.tranche_1_payee, Decimal('200000'))

    # ── Synchronisation ──────────────────────────────────────────────────────

    def test_une_suppression_appliquee_par_synchronisation_recalcule_aussi(self):
        """
        Le meme mecanisme doit jouer quand un poste applique une suppression
        recue d'un autre poste, pas seulement quand l'utilisateur agit dans
        l'interface. `apply_sync_change` enveloppe ses ecritures dans
        `mute_sync()`, qui ne coupe que la creation de nouveaux SyncChange —
        pas les autres signaux de l'application.
        """
        from synchronisation.engine import apply_sync_change
        from synchronisation.models import SyncChange

        paiement = self._payer(300000)
        object_uuid = paiement.sync_uuid
        self.assertEqual(self._rafraichir().tranche_1_payee, Decimal('300000'))

        changement = SyncChange.objects.create(
            ecole=self.ecole, model_label='paiements.Paiement',
            object_uuid=object_uuid, operation='DELETE',
            payload={'sync_uuid': str(object_uuid)},
        )
        apply_sync_change(changement)

        self.assertFalse(Paiement.objects.filter(pk=paiement.pk).exists())
        ech = self._rafraichir()
        self.assertEqual(
            ech.tranche_1_payee, Decimal('0'),
            "une suppression recue par synchronisation doit recalculer le solde "
            "exactement comme une suppression locale",
        )
