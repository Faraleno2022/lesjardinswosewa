from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from openpyxl import load_workbook

from eleves.models import Classe, Ecole, Eleve, GrilleTarifaire, Responsable
from paiements.models import EcheancierPaiement, ModePaiement, Paiement, TypePaiement
from paiements.views import _allocate_payment_to_echeancier

from .support import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class InscriptionReinscriptionReportingTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom="École ventilation",
            adresse="Conakry",
            telephone="+224620000111",
            directeur="Direction",
        )
        self.classe = Classe.objects.create(
            nom="6ème A",
            ecole=self.ecole,
            niveau="PRIMAIRE_6",
            annee_scolaire="2025-2026",
        )
        self.responsable = Responsable.objects.create(
            prenom="Parent",
            nom="Test",
            relation="PERE",
            telephone="+224620000112",
            adresse="Conakry",
        )
        GrilleTarifaire.objects.create(
            ecole=self.ecole,
            niveau=self.classe.niveau,
            annee_scolaire=self.classe.annee_scolaire,
            frais_inscription=Decimal("30000"),
            frais_reinscription=Decimal("20000"),
            tranche_1=Decimal("100000"),
            tranche_2=Decimal("100000"),
            tranche_3=Decimal("100000"),
        )
        self.user = get_user_model().objects.create_superuser(
            username="admin_ventilation",
            email="admin@example.com",
            password="pass12345",
        )
        self.client.force_login(self.user)

    def _student(self, matricule, prenom):
        return Eleve.objects.create(
            nom="Camara",
            prenom=prenom,
            matricule=matricule,
            classe=self.classe,
            sexe="F",
            date_naissance=date(2015, 1, 1),
            lieu_naissance="Conakry",
            date_inscription=date(2025, 9, 1),
            responsable_principal=self.responsable,
        )

    def _schedule(self, student, nature, fee, tranche_1=0, admission_paye=0):
        return EcheancierPaiement.objects.create(
            eleve=student,
            annee_scolaire="2025-2026",
            nature_frais=nature,
            frais_inscription_du=Decimal(str(fee)),
            tranche_1_due=Decimal(str(tranche_1)),
            tranche_2_due=0,
            tranche_3_due=0,
            frais_inscription_paye=Decimal(str(admission_paye)),
            date_echeance_inscription=date(2025, 9, 1),
            date_echeance_tranche_1=date(2026, 1, 15),
            date_echeance_tranche_2=date(2026, 3, 15),
            date_echeance_tranche_3=date(2026, 5, 15),
        )

    def test_report_columns_are_disjoint_and_total_is_not_duplicated(self):
        self._schedule(self._student("VENT-001", "Aïssata"), "INSCRIPTION", 30000)
        self._schedule(self._student("VENT-002", "Mariam"), "REINSCRIPTION", 20000)

        response = self.client.get(reverse("paiements:liste_paiements"))

        self.assertEqual(response.status_code, 200)
        totals = response.context["totaux_du"]
        self.assertEqual(totals["frais_inscription_total"], 30000)
        self.assertEqual(totals["frais_reinscription_total"], 20000)
        self.assertEqual(totals["du_global_net"], 50000)
        self.assertEqual(totals["frais_reinscription_pct"], 40.0)
        row = response.context["totaux_du_detail_classes"][0]
        self.assertEqual(row["frais_inscription_total"], 30000)
        self.assertEqual(row["frais_reinscription_total"], 20000)
        self.assertEqual(row["du_global_net"], 50000)

    def test_equal_tariffs_remain_distinguishable_by_nature(self):
        self._schedule(self._student("VENT-003", "Fatou"), "INSCRIPTION", 20000)
        self._schedule(self._student("VENT-004", "Hawa"), "REINSCRIPTION", 20000)

        response = self.client.get(reverse("paiements:liste_paiements"))
        totals = response.context["totaux_du"]

        self.assertEqual(totals["frais_inscription_total"], 20000)
        self.assertEqual(totals["frais_reinscription_total"], 20000)
        self.assertEqual(totals["du_global_net"], 40000)

    def test_excel_export_uses_the_same_disjoint_distribution(self):
        self._schedule(self._student("VENT-005", "Kadiatou"), "INSCRIPTION", 30000)
        self._schedule(self._student("VENT-006", "Nènè"), "REINSCRIPTION", 20000)

        response = self.client.get(reverse("paiements:export_recap_par_classe_excel"))

        self.assertEqual(response.status_code, 200)
        worksheet = load_workbook(BytesIO(response.content), data_only=True).active
        values = [cell.value for cell in worksheet[2]]
        self.assertEqual(values[4], 30000)
        self.assertEqual(values[5], 20000)
        self.assertEqual(values[6], 40.0)
        self.assertEqual(values[7], 50000)

    def test_tranches_exports_separate_reenrollment_from_enrollment(self):
        student = self._student("VENT-009", "Saran")
        self._schedule(
            student,
            "REINSCRIPTION",
            20000,
            tranche_1=100000,
            admission_paye=20000,
        )

        response = self.client.get(
            reverse("paiements:export_tranches_par_classe_excel"),
            {"annee_scolaire": "2025-2026", "classe": self.classe.pk},
        )

        self.assertEqual(response.status_code, 200)
        workbook = load_workbook(BytesIO(response.content), data_only=True)
        worksheet = next(ws for ws in workbook.worksheets if ws.title != "Index")
        self.assertEqual(
            [cell.value for cell in worksheet[2]],
            [
                "Élève", "Inscription payée", "Réinscription payée",
                "Tranche 1 payée", "Tranche 2 payée", "Tranche 3 payée",
                "Total dû", "Total payé", "Reste",
            ],
        )
        values = [cell.value for cell in worksheet[3]]
        self.assertEqual(values[1], 0)
        self.assertEqual(values[2], 20000)
        self.assertEqual(values[6], 120000)
        self.assertEqual(values[7], 20000)
        self.assertEqual(values[8], 100000)

    @patch("paiements.views.timezone.localdate", return_value=date(2025, 10, 1))
    def test_reenrollment_plus_first_installment_sets_nature_and_allocates(self, _localdate):
        student = self._student("VENT-007", "Binta")
        schedule = self._schedule(student, "INSCRIPTION", 30000, tranche_1=100000)
        payment_type = TypePaiement.objects.create(nom="Réinscription + Tranche 1")
        mode = ModePaiement.objects.create(nom="Espèces")
        payment = Paiement.objects.create(
            eleve=student,
            type_paiement=payment_type,
            mode_paiement=mode,
            montant=Decimal("120000"),
            date_paiement=date(2025, 10, 1),
            statut="VALIDE",
        )

        _allocate_payment_to_echeancier(payment)
        schedule.refresh_from_db()

        self.assertEqual(schedule.nature_frais, "REINSCRIPTION")
        self.assertEqual(schedule.frais_inscription_du, Decimal("20000"))
        self.assertEqual(schedule.frais_inscription_paye, Decimal("20000"))
        self.assertEqual(schedule.tranche_1_payee, Decimal("100000"))

    def test_schedule_page_displays_reenrollment_label(self):
        student = self._student("VENT-008", "M'Mah")
        self._schedule(student, "REINSCRIPTION", 20000)

        response = self.client.get(
            reverse("paiements:echeancier_eleve", args=[student.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Frais de réinscription")
        self.assertNotContains(response, ">Frais d'inscription<", html=False)
