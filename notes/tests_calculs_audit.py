"""Invariants de calcul entre moyennes, bulletins, sélections et classements."""
from decimal import Decimal

from django.core.cache import cache
from django.test import TestCase

from eleves.models import Classe, Ecole, Eleve
from .models import ClasseNote, CompositionNote, MatiereNote, NoteMensuelle, NoteSuivi
from .calculs_moyennes import (
    bonus_suivi_batch, calculer_bulletin_intelligent, calculer_classement_classe,
    calculer_moyenne_matiere, calculer_moyennes_classe_optimise,
)


class CoherenceCalculsNotesTests(TestCase):
    def setUp(self):
        cache.clear()
        self.annee = "2026-2027"
        self.ecole = Ecole.objects.create(nom="Audit calculs", adresse="Conakry",
            telephone="+224600002001", directeur="Direction", bonus_suivi_actif=True)
        self.classe = Classe.objects.create(ecole=self.ecole, nom="7ème Année",
            niveau="COLLEGE_7", annee_scolaire=self.annee)
        self.classe_note = ClasseNote.objects.create(ecole=self.ecole, nom=self.classe.nom,
            niveau="COLLEGE_7", niveau_enseignement="SECONDAIRE", annee_scolaire=self.annee)
        self.a = Eleve.objects.create(matricule="CAL-A", nom="Diallo", prenom="A",
            sexe="F", classe=self.classe, statut="ACTIF")
        self.b = Eleve.objects.create(matricule="CAL-B", nom="Barry", prenom="B",
            sexe="M", classe=self.classe, statut="ACTIF")
        self.math = MatiereNote.objects.create(classe=self.classe_note, nom="Math", code="M", coefficient=2)
        self.fr = MatiereNote.objects.create(classe=self.classe_note, nom="Français", code="F", coefficient=1)
        for eleve, matiere, note in ((self.a, self.math, 10), (self.b, self.math, 18), (self.a, self.fr, 16)):
            NoteMensuelle.objects.create(eleve=eleve, matiere=matiere, mois="OCTOBRE",
                note=note, annee_scolaire=self.annee)

    def composition(self, eleve, periode, note, absent=False):
        return CompositionNote.objects.create(eleve=eleve, matiere=self.math,
            periode=periode, note=note, absent=absent, annee_scolaire=self.annee)

    def test_bonus_primaire_ne_depasse_pas_dix_dans_les_trois_calculs(self):
        self.classe_note.nom = "CM2"
        self.classe_note.niveau_enseignement = "PRIMAIRE"
        self.classe_note.save()
        NoteSuivi.objects.create(eleve=self.a, matiere=self.math, mois="OCTOBRE",
            annee_scolaire=self.annee, type_note="COURS", note=20)
        valeurs = [
            calculer_moyenne_matiere(self.a, self.math, "OCTOBRE")["moyenne_matiere"],
            calculer_bulletin_intelligent(self.a, self.math, "OCTOBRE", "mensuel")["moyenne"],
            calculer_moyennes_classe_optimise([self.a], [self.math], "OCTOBRE", use_cache=False)[self.a.pk]["moyenne_generale"],
        ]
        for valeur in valeurs:
            with self.subTest(valeur=valeur):
                self.assertEqual(valeur, 10)

    def test_bonus_secondaire_reste_plafonne_a_vingt(self):
        note = NoteMensuelle.objects.get(eleve=self.a, matiere=self.math)
        note.note = 19
        note.save()
        NoteSuivi.objects.create(eleve=self.a, matiere=self.math, mois="OCTOBRE",
            annee_scolaire=self.annee, type_note="COURS", note=20)
        self.assertEqual(calculer_moyenne_matiere(self.a, self.math, "OCTOBRE")["moyenne_matiere"], 20)

    def test_composition_absente_ne_reprend_pas_les_trimestres(self):
        self.composition(self.a, "TRIMESTRE_1", 16)
        self.composition(self.a, "TRIMESTRE_2", 18)
        self.composition(self.a, "SEMESTRE_1", 0, absent=True)
        individuel = calculer_moyenne_matiere(self.a, self.math, "SEMESTRE_1", "semestre")
        bulletin = calculer_bulletin_intelligent(self.a, self.math, "SEMESTRE_1", "semestre")
        collectif = calculer_moyennes_classe_optimise([self.a], [self.math], "SEMESTRE_1", "semestre", use_cache=False)[self.a.pk]
        for valeur in (individuel["moyenne_matiere"], bulletin["moyenne"], collectif["moyenne_generale"]):
            with self.subTest(valeur=valeur):
                self.assertEqual(valeur, 4)  # 10 * 40 % + 0 * 60 %

    def test_repli_trimestriel_compte_une_absence_pour_zero(self):
        self.composition(self.a, "TRIMESTRE_1", 16)
        self.composition(self.a, "TRIMESTRE_2", 0, absent=True)
        result = calculer_moyenne_matiere(self.a, self.math, "SEMESTRE_1", "semestre")
        self.assertEqual(result["note_composition"], 8)
        self.assertEqual(result["moyenne_matiere"], 8.8)

    def test_composition_manquante_reste_zero_pour_un_sous_ensemble_eleves(self):
        self.composition(self.b, "TRIMESTRE_1", 18)
        individuel = calculer_moyenne_matiere(self.a, self.math, "TRIMESTRE_1", "trimestre")
        collectif = calculer_moyennes_classe_optimise([self.a], [self.math], "TRIMESTRE_1", "trimestre", use_cache=False)[self.a.pk]
        self.assertEqual(individuel["moyenne_matiere"], 4)
        self.assertEqual(collectif["moyenne_generale"], 4)

    def test_cache_moyennes_distingue_les_eleves_selectionnes(self):
        calculer_moyennes_classe_optimise([self.a], [self.math], "OCTOBRE")
        complet = calculer_moyennes_classe_optimise([self.a, self.b], [self.math], "OCTOBRE")
        self.assertEqual(set(complet), {self.a.pk, self.b.pk})
        self.assertEqual(complet[self.b.pk]["moyenne_generale"], 18)

    def test_cache_moyennes_distingue_les_matieres_selectionnees(self):
        calculer_moyennes_classe_optimise([self.a], [self.math], "OCTOBRE")
        complet = calculer_moyennes_classe_optimise([self.a], [self.math, self.fr], "OCTOBRE")
        self.assertEqual(complet[self.a.pk]["moyenne_generale"], 12)
        self.assertEqual(len(complet[self.a.pk]["details_matieres"]), 2)

    def test_cache_classement_distingue_la_selection(self):
        calculer_classement_classe([self.a], [self.math], "OCTOBRE")
        complet = calculer_classement_classe([self.a, self.b], [self.math], "OCTOBRE")
        self.assertEqual(complet["total_eleves"], 2)
        self.assertEqual(complet["rang_map"], {self.b.pk: 1, self.a.pk: 2})

    def test_cache_classement_actualise_apres_modification(self):
        calculer_classement_classe([self.a, self.b], [self.math], "OCTOBRE")
        note = NoteMensuelle.objects.get(eleve=self.a, matiere=self.math)
        note.note = 20
        note.save()
        result = calculer_classement_classe([self.a, self.b], [self.math], "OCTOBRE")
        self.assertEqual(result["rang_map"][self.a.pk], 1)

    def test_periode_lisible_et_code_donnent_les_memes_moyennes(self):
        self.composition(self.a, "TRIMESTRE_1", 18)
        for fonction in (
            lambda p: calculer_moyenne_matiere(self.a, self.math, p, "trimestre")["moyenne_matiere"],
            lambda p: calculer_bulletin_intelligent(self.a, self.math, p, "trimestre")["moyenne"],
            lambda p: calculer_moyennes_classe_optimise([self.a], [self.math], p, "trimestre", use_cache=False)[self.a.pk]["moyenne_generale"],
        ):
            with self.subTest(fonction=fonction):
                self.assertEqual(fonction("1er Trimestre"), 14.8)

    def test_bonus_nest_pas_active_par_une_autre_ecole_du_lot(self):
        autre = Ecole.objects.create(nom="Sans bonus", adresse="Conakry",
            telephone="+224600002002", directeur="Direction", bonus_suivi_actif=False)
        classe = Classe.objects.create(ecole=autre, nom="7ème Année", niveau="COLLEGE_7", annee_scolaire=self.annee)
        classe_note = ClasseNote.objects.create(ecole=autre, nom=classe.nom, niveau="COLLEGE_7",
            niveau_enseignement="SECONDAIRE", annee_scolaire=self.annee)
        matiere = MatiereNote.objects.create(classe=classe_note, nom="Math", code="M")
        eleve = Eleve.objects.create(matricule="CAL-EXT", nom="Autre", prenom="C", sexe="F", classe=classe)
        NoteSuivi.objects.create(eleve=eleve, matiere=matiere, mois="OCTOBRE",
            annee_scolaire=self.annee, type_note="COURS", note=20)
        bonus = bonus_suivi_batch([self.a.pk, eleve.pk], [self.math.pk, matiere.pk], ["OCTOBRE"], self.annee)
        self.assertNotIn((eleve.pk, matiere.pk, "OCTOBRE"), bonus)
