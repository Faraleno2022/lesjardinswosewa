from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire
from paiements.models import (
    EcheancierPaiement,
    ModePaiement,
    Paiement,
    PaiementRemise,
    RemiseReduction,
    TypePaiement,
)
from paiements.tests.support import TEST_MIDDLEWARE
from utilisateurs.models import Profil
from utilisateurs.utils import filter_by_user_school


class TransfertClassePaiementTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole transfert',
            adresse='Conakry',
            telephone='+224620000001',
            directeur='Direction',
        )
        self.ancienne_classe = Classe.objects.create(
            ecole=self.ecole,
            nom='7eme A',
            niveau='COLLEGE_7',
            annee_scolaire='2025-2026',
        )
        self.nouvelle_classe = Classe.objects.create(
            ecole=self.ecole,
            nom='8eme A',
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
        )
        self.classe_annee_suivante = Classe.objects.create(
            ecole=self.ecole,
            nom='8eme A',
            niveau='COLLEGE_8',
            annee_scolaire='2026-2027',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='Ecole destination',
            adresse='Conakry',
            telephone='+224620000099',
            directeur='Autre direction',
        )
        self.classe_autre_ecole = Classe.objects.create(
            ecole=self.autre_ecole,
            nom='8eme B',
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau='COLLEGE_7',
            annee_scolaire='2025-2026',
            frais_inscription=Decimal('100000'),
            frais_reinscription=Decimal('75000'),
            tranche_1=Decimal('500000'),
            tranche_2=Decimal('500000'),
            tranche_3=Decimal('400000'),
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
            frais_inscription=Decimal('200000'),
            frais_reinscription=Decimal('150000'),
            tranche_1=Decimal('600000'),
            tranche_2=Decimal('600000'),
            tranche_3=Decimal('400000'),
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau='COLLEGE_8',
            annee_scolaire='2026-2027',
            frais_inscription=Decimal('250000'),
            frais_reinscription=Decimal('175000'),
            tranche_1=Decimal('625000'),
            tranche_2=Decimal('625000'),
            tranche_3=Decimal('425000'),
        )
        GrilleTarifaire.objects.create(
            ecole=self.autre_ecole,
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
            frais_inscription=Decimal('200000'),
            frais_reinscription=Decimal('150000'),
            tranche_1=Decimal('600000'),
            tranche_2=Decimal('600000'),
            tranche_3=Decimal('400000'),
        )
        self.eleve = Eleve.objects.create(
            matricule='CN7-900',
            prenom='Aminata',
            nom='Diallo',
            sexe='F',
            classe=self.ancienne_classe,
            date_inscription=date(2025, 9, 1),
        )
        self.type_paiement = TypePaiement.objects.create(
            nom='Scolarite annuelle', categorie='SCOLARITE'
        )
        self.mode_paiement = ModePaiement.objects.create(nom='Especes transfert')
        self.echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve,
            annee_scolaire='2025-2026',
            frais_inscription_du=Decimal('100000'),
            tranche_1_due=Decimal('500000'),
            tranche_2_due=Decimal('500000'),
            tranche_3_due=Decimal('400000'),
            date_echeance_inscription=date(2025, 9, 30),
            date_echeance_tranche_1=date(2026, 1, 15),
            date_echeance_tranche_2=date(2026, 3, 15),
            date_echeance_tranche_3=date(2026, 5, 15),
        )

    def creer_paiement_valide(self, montant, annee='2025-2026'):
        return Paiement.objects.create(
            eleve=self.eleve,
            type_paiement=self.type_paiement,
            mode_paiement=self.mode_paiement,
            numero_recu='',
            montant=Decimal(montant),
            annee_scolaire=annee,
            date_paiement=date(2025, 10, 1),
            statut='VALIDE',
        )

    def test_meme_annee_applique_nouvelle_grille_et_conserve_le_paiement(self):
        paiement = self.creer_paiement_valide('600000')

        self.eleve.classe = self.nouvelle_classe
        self.eleve.save()
        self.echeancier.refresh_from_db()
        paiement.refresh_from_db()

        self.assertEqual(self.echeancier.total_du, Decimal('1800000'))
        self.assertEqual(self.echeancier.frais_inscription_paye, Decimal('200000'))
        self.assertEqual(self.echeancier.tranche_1_payee, Decimal('400000'))
        self.assertEqual(self.echeancier.total_paye, Decimal('600000'))
        self.assertEqual(self.echeancier.solde_restant, Decimal('1200000'))
        self.assertEqual(paiement.annee_scolaire, '2025-2026')
        self.assertEqual(
            self.eleve._financial_transfer_info['credit_non_affecte'],
            Decimal('0'),
        )

    def test_nouvelle_annee_garde_historique_et_ne_reporte_pas_le_paiement(self):
        paiement = self.creer_paiement_valide('600000')

        self.eleve.classe = self.classe_annee_suivante
        self.eleve.save()

        self.echeancier.refresh_from_db()
        nouvel_echeancier = EcheancierPaiement.objects.get(
            eleve=self.eleve,
            annee_scolaire='2026-2027',
        )
        paiement.refresh_from_db()

        self.assertEqual(self.echeancier.total_du, Decimal('1500000'))
        self.assertEqual(nouvel_echeancier.nature_frais, 'REINSCRIPTION')
        self.assertEqual(nouvel_echeancier.total_du, Decimal('1850000'))
        self.assertEqual(nouvel_echeancier.total_paye, Decimal('0'))
        self.assertEqual(paiement.annee_scolaire, '2025-2026')
        self.assertEqual(self.eleve.echeanciers.count(), 2)

    def test_tarif_inferieur_signale_un_credit_sans_perdre_le_paiement(self):
        GrilleTarifaire.objects.filter(
            ecole=self.ecole,
            niveau='COLLEGE_8',
            annee_scolaire='2025-2026',
        ).update(
            frais_inscription=Decimal('100000'),
            tranche_1=Decimal('200000'),
            tranche_2=Decimal('100000'),
            tranche_3=Decimal('100000'),
        )
        self.creer_paiement_valide('600000')

        self.eleve.classe = self.nouvelle_classe
        self.eleve.save()
        self.echeancier.refresh_from_db()

        self.assertEqual(self.echeancier.total_du, Decimal('500000'))
        self.assertEqual(self.echeancier.total_paye, Decimal('500000'))
        self.assertEqual(self.echeancier.statut, 'PAYE_COMPLET')
        self.assertEqual(
            self.eleve._financial_transfer_info['credit_non_affecte'],
            Decimal('100000'),
        )
        total = Paiement.objects.filter(
            eleve=self.eleve, statut='VALIDE'
        ).aggregate(total=Sum('montant'))['total']
        self.assertEqual(total, Decimal('600000'))

    def test_meme_annee_reaffecte_aussi_la_remise_validee(self):
        paiement = self.creer_paiement_valide('600000')
        remise = RemiseReduction.objects.create(
            nom='Remise transfert',
            type_remise='MONTANT_FIXE',
            valeur=Decimal('100000'),
            motif='SOCIALE',
            date_debut=date(2025, 9, 1),
            date_fin=date(2026, 8, 31),
            actif=True,
        )
        PaiementRemise.objects.create(
            paiement=paiement,
            remise=remise,
            montant_remise=Decimal('100000'),
            motif='GESTE_COMMERCIAL',
            tranches_concernees='1',
        )

        self.eleve.classe = self.nouvelle_classe
        self.eleve.save()
        self.echeancier.refresh_from_db()

        self.assertEqual(self.echeancier.total_paye, Decimal('600000'))
        self.assertEqual(self.echeancier.total_remises_valides, Decimal('100000'))
        self.assertEqual(self.echeancier.solde_restant, Decimal('1100000'))
        self.assertEqual(
            self.eleve._financial_transfer_info['remises_conservees'],
            Decimal('100000'),
        )

    def test_absence_de_grille_nefface_pas_lancien_echeancier(self):
        classe_sans_grille = Classe.objects.create(
            ecole=self.ecole,
            nom='9eme A',
            niveau='COLLEGE_9',
            annee_scolaire='2025-2026',
        )
        self.creer_paiement_valide('600000')

        self.eleve.classe = classe_sans_grille
        self.eleve.save()
        self.echeancier.refresh_from_db()

        self.assertTrue(self.eleve._financial_transfer_info['grille_manquante'])
        self.assertEqual(self.echeancier.total_du, Decimal('1500000'))
        self.assertEqual(self.echeancier.total_paye, Decimal('600000'))

    def test_transfert_inter_ecoles_conserve_le_recu_dans_lecole_dencaissement(self):
        paiement = self.creer_paiement_valide('600000')
        self.assertEqual(paiement.ecole_encaissement, self.ecole)
        self.assertEqual(paiement.classe_encaissement, self.ancienne_classe)

        self.eleve.classe = self.classe_autre_ecole
        self.eleve.save()
        paiement.refresh_from_db()

        self.assertEqual(self.eleve.classe.ecole, self.autre_ecole)
        self.assertEqual(paiement.ecole_encaissement, self.ecole)
        self.assertEqual(paiement.classe_encaissement, self.ancienne_classe)
        self.assertTrue(Paiement.objects.pour_ecole(self.ecole).filter(pk=paiement.pk).exists())
        self.assertFalse(
            Paiement.objects.pour_ecole(self.autre_ecole).filter(pk=paiement.pk).exists()
        )

        User = get_user_model()
        utilisateur = User.objects.create_user('comptable-origine')
        Profil.objects.update_or_create(
            user=utilisateur,
            defaults={
                'role': 'COMPTABLE',
                'telephone': '+224620000088',
                'ecole': self.ecole,
            },
        )
        utilisateur = User.objects.get(pk=utilisateur.pk)
        visibles = filter_by_user_school(
            Paiement.objects.all(), utilisateur, 'eleve__classe__ecole'
        )
        self.assertTrue(visibles.filter(pk=paiement.pk).exists())


    def preparer_transfert_a_b_avec_remise(self):
        classe_b = Classe.objects.create(
            ecole=self.ecole, nom='7eme B', niveau='COLLEGE_7',
            annee_scolaire='2025-2026',
        )
        premier = self.creer_paiement_valide('600000')
        remise = RemiseReduction.objects.create(
            nom='Bourse première tranche', type_remise='MONTANT_FIXE',
            valeur=100000, motif='SOCIALE', date_debut=date(2025, 9, 1),
            date_fin=date(2026, 8, 31),
        )
        ligne = PaiementRemise.objects.create(
            paiement=premier, remise=remise, montant_remise=100000,
            tranches_concernees='1', deduite_du_paiement=True,
        )
        second = self.creer_paiement_valide('400000')
        return classe_b, premier, second, ligne

    @override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
    def test_transfert_a_b_par_interface_conserve_solde_remise_et_actualise_cartes(self):
        from paiements.services import calculer_situation_echeancier
        from paiements.carnet_paiement import collecter_carnet_paiement
        classe_b, premier, second, remise = self.preparer_transfert_a_b_avec_remise()
        echeancier_id = self.echeancier.pk
        numero_recu = premier.numero_recu
        self.client.force_login(get_user_model().objects.create_superuser(
            'transfert-a-b', 'transfert@example.test', 'secret',
        ))
        # Un autre élève de A ne doit pas changer de classe.
        autre = Eleve.objects.create(
            matricule='CN7-901', prenom='Moussa', nom='Bah', sexe='M',
            classe=self.ancienne_classe,
        )
        response = self.client.post(reverse('eleves:repartir_eleves'), {
            'eleve_id': self.eleve.pk, 'ancienne_classe_id': self.ancienne_classe.pk,
            'classe_id': classe_b.pk, 'action': 'enregistrer',
        })
        self.assertEqual(response.status_code, 302)
        self.eleve.refresh_from_db()
        autre.refresh_from_db()
        self.echeancier.refresh_from_db()
        premier.refresh_from_db()
        remise.refresh_from_db()
        self.assertEqual(self.eleve.classe_id, classe_b.pk)
        self.assertEqual(autre.classe_id, self.ancienne_classe.pk)
        self.assertEqual(self.eleve.echeanciers.count(), 1)
        self.assertEqual(self.echeancier.pk, echeancier_id)
        self.assertEqual(self.echeancier.total_du, 1500000)
        self.assertEqual(self.echeancier.total_paye, 1000000)
        self.assertEqual(self.echeancier.total_remises_valides, 100000)
        self.assertEqual(self.echeancier.solde_restant, 400000)
        self.assertEqual(premier.montant, 600000)
        self.assertEqual(premier.numero_recu, numero_recu)
        self.assertEqual(premier.classe_encaissement_id, self.ancienne_classe.pk)
        self.assertEqual(remise.montant_remise, 100000)
        self.assertEqual(calculer_situation_echeancier(self.echeancier)['reste'], 400000)
        self.assertEqual(collecter_carnet_paiement(second)['reste_final'], 400000)
        fiche = self.client.get(reverse('paiements:echeancier_eleve', args=[self.eleve.pk]))
        self.assertEqual(fiche.context['finance_eleve']['reste_a_payer'], 400000)
        dashboard = self.client.get(reverse('paiements:tableau_bord'))
        classes = {c['classe_id']: c for c in dashboard.context['classes_a_risque']}
        self.assertIn(classe_b.pk, classes)
        self.assertNotIn(self.ancienne_classe.pk, classes)
        self.assertEqual(classes[classe_b.pk]['total_encaisse'], 1000000)
        self.assertEqual(classes[classe_b.pk]['reste'], 400000)
        # Le retour B vers A ne doit rejouer ni l'admission ni la remise.
        self.eleve.classe = self.ancienne_classe
        self.eleve.save()
        self.echeancier.refresh_from_db()
        self.assertEqual(self.echeancier.solde_restant, 400000)
        self.assertEqual(self.eleve.paiements.count(), 2)

    def test_corrections_apres_transfert_a_b_recalculent_le_dossier_courant(self):
        classe_b, premier, second, remise = self.preparer_transfert_a_b_avec_remise()
        self.eleve.classe = classe_b
        self.eleve.save()
        second.montant = 300000
        second.save()
        self.echeancier.refresh_from_db()
        self.assertEqual(self.echeancier.total_paye, 900000)
        self.assertEqual(self.echeancier.total_remises_valides, 100000)
        self.assertEqual(self.echeancier.solde_restant, 500000)
        premier.statut = 'ANNULE'
        premier.save()
        self.echeancier.refresh_from_db()
        self.assertEqual(self.echeancier.total_paye, 300000)
        self.assertEqual(self.echeancier.total_remises_valides, 0)
        self.assertEqual(self.echeancier.solde_restant, 1200000)
        premier.statut = 'VALIDE'
        premier.save()
        second.delete()
        self.echeancier.refresh_from_db()
        self.assertEqual(self.echeancier.total_paye, 600000)
        self.assertEqual(self.echeancier.total_remises_valides, 100000)
        self.assertEqual(self.echeancier.solde_restant, 800000)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.classe_id, classe_b.pk)

    def test_transfert_a_b_conserve_le_tarif_de_reinscription(self):
        classe_b, premier, second, remise = self.preparer_transfert_a_b_avec_remise()
        premier.type_paiement = TypePaiement.objects.create(
            nom='Réinscription et scolarité', categorie='SCOLARITE',
        )
        premier.save()
        self.eleve.classe = classe_b
        self.eleve.save()
        self.echeancier.refresh_from_db()
        self.assertEqual(self.echeancier.nature_frais, 'REINSCRIPTION')
        self.assertEqual(self.echeancier.frais_inscription_du, 75000)
        self.assertEqual(self.echeancier.total_du, 1475000)
        self.assertEqual(self.echeancier.total_paye, 1000000)
        self.assertEqual(self.echeancier.total_remises_valides, 100000)
        self.assertEqual(self.echeancier.solde_restant, 375000)
