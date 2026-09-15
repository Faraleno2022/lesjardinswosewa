"""Conservation et arrondis de la ventilation des heures de paie."""
from decimal import Decimal
from django.test import SimpleTestCase
from .services import arrondir_heures, arrondir_montant, repartir_heures


class RepartitionHeuresAuditTests(SimpleTestCase):
    def test_petites_durees_ne_produisent_jamais_dheures_negatives(self):
        for total in ("0.01", "0.02", "0.03", "0.05", "1.00"):
            for nombre in range(2, 10):
                with self.subTest(total=total, nombre=nombre):
                    lignes = [(index, Decimal("1")) for index in range(nombre)]
                    resultat = repartir_heures(Decimal(total), lignes)
                    self.assertTrue(all(heures >= 0 for _, _, heures in resultat))
                    self.assertEqual(sum(h for _, _, h in resultat), Decimal(total))

    def test_affectation_sans_heures_ne_recoit_pas_le_reliquat(self):
        resultat = repartir_heures(Decimal("1"), [(0, Decimal("1")), (1, Decimal("1")),
                                                  (2, Decimal("1")), (3, Decimal("0"))])
        self.assertEqual(resultat[-1][2], 0)
        self.assertEqual(sum(h for _, _, h in resultat), 1)

    def test_arrondi_decimal_est_identique_pour_decimal_et_float(self):
        for fonction in (arrondir_heures, arrondir_montant):
            with self.subTest(fonction=fonction.__name__):
                self.assertEqual(fonction(2.675), Decimal("2.68"))
                self.assertEqual(fonction(Decimal("2.675")), Decimal("2.68"))
