from django.test import SimpleTestCase
from eleves.models import Classe, _code_classe_from_nom_ou_niveau, _normalize_code_prefixe


class CodesMatriculesAuditTests(SimpleTestCase):
    def test_code_explicite_prioritaire(self):
        self.assertEqual(_code_classe_from_nom_ou_niveau(Classe(nom="CM2", niveau="PRIMAIRE_6", code_matricule=" SPECIAL ")), "SPECIAL")

    def test_codes_sans_configuration_manuelle(self):
        for nom, niveau, code in (("Petite section", "MATERNELLE", "MPS"), ("11ème série littéraire", "LYCEE_11", "L11SL"), ("Classe A", "PRIMAIRE_3", "PN3"), ("Classe inconnue", "INCONNU", "")):
            with self.subTest(nom=nom):
                self.assertEqual(_code_classe_from_nom_ou_niveau(Classe(nom=nom, niveau=niveau)), code)

    def test_prefixe_ecole_independant_du_code_classe(self):
        self.assertEqual(_normalize_code_prefixe(" ECOLE / ECOLE / "), "ECOLE/")
        self.assertEqual(_normalize_code_prefixe(""), "")
