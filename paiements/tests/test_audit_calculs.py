"""Conservation des encaissements et arrondi des remises en GNF."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase

from eleves.models import Classe, Ecole, Eleve
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, RemiseReduction, TypePaiement
from paiements.reporting import repartir_encaissements


class ArrondiRemisesAuditTests(SimpleTestCase):
    def test_remise_fixe_arrondie_au_gnf_comme_un_pourcentage(self):
        remise = RemiseReduction(type_remise="MONTANT_FIXE", valeur=Decimal("10.50"))
        self.assertEqual(remise.calculer_remise(Decimal("100")), Decimal("11"))
        self.assertEqual(remise.calculer_remise(Decimal("10")), Decimal("10"))


class EncaissementsAuditTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(nom="Audit encaissements", adresse="Conakry",
            telephone="+224600003001", directeur="Direction")
        self.classe = Classe.objects.create(ecole=self.ecole, nom="CM2", niveau="PRIMAIRE_6", annee_scolaire="2026-2027")
        self.eleve = Eleve.objects.create(matricule="ENC-AUD", nom="Diallo", prenom="Test", sexe="F", classe=self.classe)
        self.type_scolarite = TypePaiement.objects.create(nom="Scolarité annuelle", categorie="SCOLARITE")
        self.autre_type = TypePaiement.objects.create(nom="Autre prestation", categorie="AUTRE")
        self.mode = ModePaiement.objects.create(nom="Espèces")
        self.echeancier = EcheancierPaiement.objects.create(
            eleve=self.eleve, annee_scolaire="2026-2027", frais_inscription_du=100,
            tranche_1_due=1000, tranche_2_due=0, tranche_3_due=0,
            date_echeance_inscription=date(2026, 9, 30), date_echeance_tranche_1=date(2026, 10, 31),
            date_echeance_tranche_2=date(2027, 1, 31), date_echeance_tranche_3=date(2027, 4, 30))

    def paiement(self, montant, type_paiement=None, statut="VALIDE"):
        return Paiement.objects.create(eleve=self.eleve, type_paiement=type_paiement or self.type_scolarite,
            montant=montant, mode_paiement=self.mode, statut=statut,
            date_paiement=date(2026, 9, 15), annee_scolaire="2026-2027")

    def test_tarif_reduit_ne_fait_pas_disparaitre_les_encaissements_des_rapports(self):
        paiement = self.paiement(1100)
        self.echeancier.tranche_1_due = 500
        self.echeancier.save()
        resultat = repartir_encaissements([paiement])
        self.assertEqual(resultat["frais_inscription"], 100)
        self.assertEqual(resultat["scolarite"], 1000)
        self.assertEqual(sum(resultat.values()), paiement.montant)

    def test_recu_entierement_en_surplus_reste_dans_les_encaissements(self):
        self.paiement(500)
        surplus = self.paiement(200)
        self.echeancier.tranche_1_due = 300
        self.echeancier.save()
        self.assertEqual(sum(repartir_encaissements([surplus]).values()), 200)

    def test_paiement_non_valide_nentre_dans_aucun_encaissement(self):
        for type_paiement in (self.type_scolarite, self.autre_type):
            for statut in ("EN_ATTENTE", "ANNULE"):
                with self.subTest(type=type_paiement.nom, statut=statut):
                    paiement = self.paiement(100, type_paiement, statut)
                    self.assertEqual(sum(repartir_encaissements([paiement]).values()), 0)
