from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from eleves.models import Classe, Ecole, Eleve, Responsable
from paiements.models import (
    EcheancierPaiement,
    ModePaiement,
    Paiement,
    PaiementRemise,
    RemiseReduction,
    TypePaiement,
)
from paiements.views import (
    _auto_validate_echeancier_for_eleve,
    _suggestion_paiement,
    _valider_paiement_impl,
    ensure_echeancier_for_eleve,
)


class MoteurPaiementRegressionsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='audit-paiements',
            email='audit-paiements@example.com',
            password='mot-de-passe-test',
        )
        self.ecole = Ecole.objects.create(
            nom='Ecole test paiements',
            adresse='Conakry',
            telephone='+224620000000',
            directeur='Direction test',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='Classe test',
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
        )
        self.responsable = Responsable.objects.create(
            prenom='Parent',
            nom='Test',
            relation='PERE',
            telephone='+224621000000',
        )
        self.eleve = Eleve.objects.create(
            matricule='PAY-001',
            prenom='Eleve',
            nom='Test',
            sexe='F',
            date_naissance=date(2014, 1, 1),
            classe=self.classe,
            date_inscription=date(2025, 9, 1),
            responsable_principal=self.responsable,
        )
        self.type_paiement = TypePaiement.objects.create(nom='Scolarite annuelle')
        self.mode = ModePaiement.objects.create(nom='Especes')
        self.echeancier = self.creer_echeancier('2025-2026')

    def creer_echeancier(self, annee_scolaire):
        return EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire=annee_scolaire,
            frais_inscription_du=Decimal('0'),
            tranche_1_due=Decimal('1000000'),
            tranche_2_due=Decimal('0'),
            tranche_3_due=Decimal('0'),
            date_echeance_inscription=date(2025, 9, 30),
            date_echeance_tranche_1=date(2026, 1, 10),
            date_echeance_tranche_2=date(2026, 3, 5),
            date_echeance_tranche_3=date(2026, 5, 5),
        )

    def creer_paiement(self, montant, statut='EN_ATTENTE', numero=None, annee='2025-2026'):
        return Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type_paiement,
            mode_paiement=self.mode,
            numero_recu=numero or '',
            montant=Decimal(montant),
            annee_scolaire=annee,
            date_paiement=date(2025, 10, 1),
            statut=statut,
            cree_par=self.user,
        )

    def test_suggestion_deduit_les_remises_validees(self):
        paiement = self.creer_paiement('400000', statut='VALIDE')
        remise = RemiseReduction.objects.create(
            nom='Remise test',
            type_remise='MONTANT_FIXE',
            valeur=Decimal('100000'),
            motif='SOCIALE',
            date_debut=date(2025, 1, 1),
            date_fin=date(2026, 12, 31),
        )
        PaiementRemise.objects.create(
            paiement=paiement,
            remise=remise,
            montant_remise=Decimal('100000'),
            motif='GESTE_COMMERCIAL',
            tranches_concernees='1',
            base_calcul='TRANCHES_DUES',
        )
        _auto_validate_echeancier_for_eleve(
            self.eleve,
            preserve_recorded=False,
            annee_scolaire='2025-2026',
            strict=True,
        )
        self.echeancier.refresh_from_db()

        suggestion = _suggestion_paiement(self.echeancier, 'scolarite annuelle')

        self.assertEqual(suggestion['suggested'], 500000)
        self.assertEqual(suggestion['echeancier']['solde_restant'], 500000)

    def test_un_paiement_ancien_ne_solde_pas_la_nouvelle_annee(self):
        self.creer_paiement('1000000', statut='VALIDE')
        _auto_validate_echeancier_for_eleve(
            self.eleve,
            preserve_recorded=False,
            annee_scolaire='2025-2026',
            strict=True,
        )
        self.classe.annee_scolaire = '2026-2027'
        self.classe.save(update_fields=['annee_scolaire'])
        self.eleve.refresh_from_db()
        nouvel_echeancier = self.creer_echeancier('2026-2027')

        _auto_validate_echeancier_for_eleve(
            self.eleve,
            preserve_recorded=False,
            annee_scolaire='2026-2027',
            strict=True,
        )
        nouvel_echeancier.refresh_from_db()

        self.assertEqual(nouvel_echeancier.total_paye, Decimal('0'))
        self.assertEqual(nouvel_echeancier.statut, 'EN_RETARD')
        self.assertEqual(self.eleve.echeancier.pk, nouvel_echeancier.pk)
        self.assertEqual(self.eleve.echeanciers.count(), 2)

    def test_creation_nouvelle_annee_preserve_l_historique(self):
        self.classe.annee_scolaire = '2026-2027'
        self.classe.save(update_fields=['annee_scolaire'])
        self.eleve.refresh_from_db()

        nouveau = ensure_echeancier_for_eleve(
            self.eleve,
            annee_scolaire='2026-2027',
        )

        self.assertEqual(nouveau.annee_scolaire, '2026-2027')
        self.assertTrue(
            EcheancierPaiement.objects.filter(
                pk=self.echeancier.pk,
                annee_scolaire='2025-2026',
            ).exists()
        )

    def test_deux_validations_ne_peuvent_pas_surpayer(self):
        premier = self.creer_paiement('700000')
        second = self.creer_paiement('700000')

        _valider_paiement_impl(premier, self.user)
        with self.assertRaises(ValidationError):
            _valider_paiement_impl(second, self.user)

        premier.refresh_from_db()
        second.refresh_from_db()
        self.echeancier.refresh_from_db()
        self.assertEqual(premier.statut, 'VALIDE')
        self.assertEqual(second.statut, 'EN_ATTENTE')
        self.assertEqual(self.echeancier.total_paye, Decimal('700000'))

    def test_erreur_allocation_annule_aussi_la_validation(self):
        paiement = self.creer_paiement('300000')

        with patch(
            'paiements.views._allocate_payment_to_echeancier',
            side_effect=RuntimeError('allocation impossible'),
        ):
            with self.assertRaises(RuntimeError):
                _valider_paiement_impl(paiement, self.user)

        paiement.refresh_from_db()
        self.echeancier.refresh_from_db()
        self.assertEqual(paiement.statut, 'EN_ATTENTE')
        self.assertEqual(self.echeancier.total_paye, Decimal('0'))

    def test_montant_negatif_est_refuse_hors_formulaire(self):
        with self.assertRaises(ValidationError):
            self.creer_paiement('-1')
