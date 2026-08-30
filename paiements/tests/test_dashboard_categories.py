from datetime import date
from decimal import Decimal
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from bus.models import AbonnementBus, AbonnementCantine
from eleves.models import Classe, Ecole, Eleve
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement
from paiements.reporting import ventiler_encaissements_par_paiement
from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class DashboardCategoryIndicatorsTests(TestCase):
    today = date(2026, 8, 26)  # mercredi

    def setUp(self):
        self.ecole = self._ecole('École principale', '+224620100001')
        self.autre_ecole = self._ecole('Autre école', '+224620100002')
        self.classe = self._classe(self.ecole, '6ème A')
        self.autre_classe = self._classe(self.autre_ecole, '6ème B')
        self.user = get_user_model().objects.create_user(
            username='comptable_dashboard',
            password='pass12345',
        )
        profil = self.user.profil
        profil.role = 'COMPTABLE'
        profil.telephone = '+224620100003'
        profil.ecole = self.ecole
        profil.is_validated = True
        profil.save(update_fields=['role', 'telephone', 'ecole', 'is_validated'])
        self.client.force_login(self.user)
        session = self.client.session
        session['phone_verified'] = True
        session['phone_verified_at'] = time.time()
        session.save()
        self.mode = ModePaiement.objects.create(nom='Espèces dashboard')
        self.types = {
            'scolarite': TypePaiement.objects.create(
                nom='Inscription + Scolarité tranche 1', categorie='SCOLARITE'
            ),
            'reinscription': TypePaiement.objects.create(
                nom='Réinscription + Scolarité tranche 1', categorie='SCOLARITE'
            ),
            'transport': TypePaiement.objects.create(
                nom='Bus scolaire', categorie='TRANSPORT'
            ),
            'cantine': TypePaiement.objects.create(
                nom='Cantine mensuelle', categorie='CANTINE'
            ),
        }

    def _ecole(self, nom, telephone):
        return Ecole.objects.create(
            nom=nom,
            adresse='Conakry',
            telephone=telephone,
            directeur='Direction',
        )

    def _classe(self, ecole, nom):
        return Classe.objects.create(
            nom=nom,
            ecole=ecole,
            niveau='PRIMAIRE_6',
            annee_scolaire='2025-2026',
        )

    def _eleve(self, matricule, classe=None):
        return Eleve.objects.create(
            nom='Camara',
            prenom=matricule,
            matricule=matricule,
            classe=classe or self.classe,
            sexe='F',
        )

    def _echeancier(self, eleve, nature, admission, tranche_1):
        return EcheancierPaiement.objects.create(
            eleve=eleve,
            annee_scolaire='2025-2026',
            nature_frais=nature,
            frais_inscription_du=Decimal(str(admission)),
            tranche_1_due=Decimal(str(tranche_1)),
            tranche_2_due=0,
            tranche_3_due=0,
            date_echeance_inscription=date(2025, 9, 1),
            date_echeance_tranche_1=date(2026, 1, 15),
            date_echeance_tranche_2=date(2026, 3, 15),
            date_echeance_tranche_3=date(2026, 5, 15),
        )

    def _paiement(self, eleve, type_key, montant, payment_date, receipt, statut='VALIDE'):
        return Paiement.objects.create(
            eleve=eleve,
            type_paiement=self.types[type_key],
            mode_paiement=self.mode,
            numero_recu=receipt,
            montant=Decimal(str(montant)),
            annee_scolaire='2025-2026',
            date_paiement=payment_date,
            statut=statut,
        )

    def _categories(self, response):
        return {
            categorie['key']: categorie
            for categorie in response.context['indicateurs_categories']
        }

    def _periods(self, categorie):
        return {
            periode['key']: periode
            for periode in categorie['periodes']
        }

    @patch('django.utils.timezone.localdate')
    def test_cards_split_receipts_and_calculate_all_periods(self, localdate):
        localdate.return_value = self.today
        inscrit = self._eleve('DASH-001')
        reinscrit = self._eleve('DASH-002')
        sans_echeancier = self._eleve('DASH-003')
        self._echeancier(inscrit, 'INSCRIPTION', 30000, 100000)
        self._echeancier(reinscrit, 'REINSCRIPTION', 20000, 100000)

        # Un reçu mixte ne doit pas gonfler la carte Inscription.
        self._paiement(inscrit, 'scolarite', 80000, self.today, 'DASH-001')
        paiement_reinscription = self._paiement(
            reinscrit, 'reinscription', 70000, date(2026, 8, 24), 'DASH-002'
        )
        self._paiement(
            sans_echeancier, 'scolarite', 40000, date(2026, 8, 10), 'DASH-003'
        )
        self._paiement(
            sans_echeancier, 'scolarite', 25000, date(2026, 1, 10), 'DASH-004'
        )

        self._paiement(inscrit, 'transport', 10000, self.today, 'DASH-BUS-01')
        self._paiement(
            inscrit, 'transport', 15000, date(2026, 8, 10), 'DASH-BUS-02'
        )
        self._paiement(
            inscrit, 'cantine', 8000, date(2026, 8, 24), 'DASH-CAN-01'
        )
        self._paiement(
            inscrit, 'cantine', 12000, date(2026, 1, 12), 'DASH-CAN-02'
        )
        self._paiement(
            inscrit,
            'transport',
            999000,
            self.today,
            'DASH-PENDING',
            statut='EN_ATTENTE',
        )

        # Ce paiement valide appartient à une autre école et doit rester invisible.
        autre_eleve = self._eleve('DASH-OTHER', self.autre_classe)
        self._paiement(
            autre_eleve, 'transport', 888000, self.today, 'DASH-OTHER'
        )

        ventilation_reinscription = ventiler_encaissements_par_paiement(
            [paiement_reinscription]
        )[paiement_reinscription.pk]
        self.assertEqual(ventilation_reinscription['frais_inscription'], Decimal('0'))
        self.assertEqual(ventilation_reinscription['reinscription'], Decimal('20000'))

        response = self.client.get(reverse('paiements:tableau_bord'))

        self.assertEqual(response.status_code, 200, getattr(response, 'url', ''))
        categories = self._categories(response)
        scolarite = self._periods(categories['scolarite'])
        self.assertEqual(scolarite['jour']['montant'], Decimal('50000'))
        self.assertEqual(scolarite['semaine']['montant'], Decimal('100000'))
        self.assertEqual(scolarite['mois']['montant'], Decimal('140000'))
        self.assertEqual(scolarite['annee']['montant'], Decimal('165000'))
        self.assertEqual(scolarite['annee']['nombre'], 4)

        inscription = self._periods(categories['inscription'])
        reinscription = self._periods(categories['reinscription'])
        self.assertEqual(inscription['jour']['montant'], Decimal('30000'))
        self.assertEqual(inscription['annee']['montant'], Decimal('30000'))
        self.assertEqual(reinscription['jour']['montant'], Decimal('0'))
        self.assertEqual(reinscription['semaine']['montant'], Decimal('20000'))
        self.assertEqual(reinscription['annee']['nombre'], 1)

        transport = self._periods(categories['transport'])
        cantine = self._periods(categories['cantine'])
        self.assertEqual(transport['jour']['montant'], Decimal('10000'))
        self.assertEqual(transport['mois']['montant'], Decimal('25000'))
        self.assertEqual(cantine['semaine']['montant'], Decimal('8000'))
        self.assertEqual(cantine['annee']['montant'], Decimal('20000'))
        self.assertContains(response, 'Encaissements par catégorie')
        self.assertContains(response, 'Réinscription')

    @patch('django.utils.timezone.localdate')
    def test_overdue_cards_use_school_debt_and_latest_subscriptions(self, localdate):
        localdate.return_value = self.today
        eleve_scolarite = self._eleve('DASH-LATE-SCO')
        eleve_bus_renouvele = self._eleve('DASH-BUS-OK')
        eleve_bus_retard = self._eleve('DASH-BUS-LATE')
        eleve_cantine_retard = self._eleve('DASH-CAN-LATE')
        self._echeancier(eleve_scolarite, 'INSCRIPTION', 30000, 100000)
        self._paiement(
            eleve_scolarite,
            'scolarite',
            80000,
            self.today,
            'DASH-LATE-PAY',
        )

        # Un ancien abonnement expiré n'est plus un retard s'il a été renouvelé.
        AbonnementBus.objects.create(
            eleve=eleve_bus_renouvele,
            montant=30000,
            date_debut=date(2026, 6, 1),
            date_expiration=date(2026, 6, 30),
            statut='EXPIRE',
        )
        AbonnementBus.objects.create(
            eleve=eleve_bus_renouvele,
            montant=40000,
            date_debut=date(2026, 8, 1),
            date_expiration=date(2026, 9, 30),
            statut='ACTIF',
        )
        AbonnementBus.objects.create(
            eleve=eleve_bus_retard,
            montant=50000,
            date_debut=date(2026, 7, 1),
            date_expiration=date(2026, 7, 31),
            statut='EXPIRE',
        )
        AbonnementCantine.objects.create(
            eleve=eleve_cantine_retard,
            montant=25000,
            date_debut=date(2026, 7, 1),
            date_expiration=date(2026, 7, 31),
            statut='EXPIRE',
        )
        autre = self._eleve('DASH-LATE-OTHER', self.autre_classe)
        AbonnementBus.objects.create(
            eleve=autre,
            montant=999000,
            date_debut=date(2026, 7, 1),
            date_expiration=date(2026, 7, 31),
            statut='EXPIRE',
        )

        response = self.client.get(reverse('paiements:tableau_bord'))

        self.assertEqual(response.status_code, 200, getattr(response, 'url', ''))
        categories = self._categories(response)
        self.assertEqual(categories['scolarite']['retard']['montant'], Decimal('50000'))
        self.assertEqual(categories['scolarite']['retard']['nombre'], 1)
        self.assertEqual(categories['transport']['retard']['montant'], Decimal('50000'))
        self.assertEqual(categories['transport']['retard']['nombre'], 1)
        self.assertEqual(categories['cantine']['retard']['montant'], Decimal('25000'))
        self.assertEqual(categories['cantine']['retard']['nombre'], 1)
        self.assertContains(response, 'Retard de paiement', count=3)

    @patch('django.utils.timezone.localdate')
    def test_bus_and_cantine_subscriptions_feed_payment_cards(self, localdate):
        localdate.return_value = self.today
        eleve = self._eleve('DASH-ABO-001')
        autre = self._eleve('DASH-ABO-OTHER', self.autre_classe)
        AbonnementBus.objects.create(
            eleve=eleve,
            montant=Decimal('45000'),
            reference_externe='BUS-REC-001',
            date_debut=self.today,
            date_expiration=date(2026, 9, 26),
        )
        AbonnementCantine.objects.create(
            eleve=eleve,
            montant=Decimal('30000'),
            reference_externe='CAN-REC-001',
            date_debut=date(2026, 8, 24),
            date_expiration=date(2026, 9, 24),
        )
        AbonnementBus.objects.create(
            eleve=autre,
            montant=Decimal('999000'),
            date_debut=self.today,
            date_expiration=date(2026, 9, 26),
        )

        response = self.client.get(reverse('paiements:tableau_bord'))

        self.assertEqual(response.status_code, 200, getattr(response, 'url', ''))
        categories = self._categories(response)
        transport = self._periods(categories['transport'])
        cantine = self._periods(categories['cantine'])
        self.assertEqual(transport['jour']['montant'], Decimal('45000'))
        self.assertEqual(transport['jour']['nombre'], 1)
        self.assertEqual(cantine['semaine']['montant'], Decimal('30000'))
        self.assertEqual(cantine['semaine']['nombre'], 1)
