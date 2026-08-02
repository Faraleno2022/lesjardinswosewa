from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import Http404
from django.test import RequestFactory, SimpleTestCase, TestCase

from eleves.models import Classe, Ecole, Eleve

from .classes_utils import normaliser_nom_classe, trouver_classe_eleve
from .models import ClasseNote
from .views import gerer_eleves


class NormalisationClasseTests(SimpleTestCase):
    def test_normalisation_ignore_accents_casse_et_ponctuation(self):
        self.assertEqual(normaliser_nom_classe('  CRÈCHE-A  '), 'creche a')


class CorrespondanceClasseElevesTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='École test',
            adresse='Conakry',
            telephone='+224620100001',
            directeur='Direction',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='Autre école',
            adresse='Conakry',
            telephone='+224620100002',
            directeur='Direction',
        )

    def creer_eleve_actif(self, classe, matricule):
        return Eleve.objects.create(
            matricule=matricule,
            prenom='Aminata',
            nom='Diallo',
            sexe='F',
            classe=classe,
            statut='ACTIF',
        )

    def creer_classe_note(self, ecole=None):
        return ClasseNote.objects.create(
            ecole=ecole or self.ecole,
            nom='CRECHE',
            niveau='GARDERIE',
            niveau_enseignement='MATERNELLE',
            annee_scolaire='2025-2026',
        )

    def test_creche_retrouve_classe_avec_accent(self):
        classe_note = self.creer_classe_note()
        classe = Classe.objects.create(
            ecole=self.ecole,
            nom='Crèche',
            niveau='GARDERIE',
            annee_scolaire='2025-2026',
        )
        self.creer_eleve_actif(classe, 'CRE-001')

        self.assertEqual(trouver_classe_eleve(classe_note), classe)

    def test_classe_avec_eleves_est_preferee_a_ancienne_classe_vide(self):
        classe_note = self.creer_classe_note()
        Classe.objects.create(
            ecole=self.ecole,
            nom='CRECHE',
            niveau='GARDERIE',
            annee_scolaire='2025-2026',
        )
        classe_actuelle = Classe.objects.create(
            ecole=self.ecole,
            nom='Crèche',
            niveau='GARDERIE',
            annee_scolaire='2026-2027',
        )
        self.creer_eleve_actif(classe_actuelle, 'CRE-002')

        self.assertEqual(trouver_classe_eleve(classe_note), classe_actuelle)

    def test_niveau_unique_permet_de_lier_creche_et_garderie(self):
        classe_note = self.creer_classe_note()
        garderie = Classe.objects.create(
            ecole=self.ecole,
            nom='Petite enfance',
            niveau='GARDERIE',
            annee_scolaire='2025-2026',
        )
        self.creer_eleve_actif(garderie, 'GAR-001')

        self.assertEqual(trouver_classe_eleve(classe_note), garderie)

    def test_classe_d_un_autre_etablissement_n_est_jamais_utilisee(self):
        classe_note = self.creer_classe_note()
        classe_externe = Classe.objects.create(
            ecole=self.autre_ecole,
            nom='CRECHE',
            niveau='GARDERIE',
            annee_scolaire='2025-2026',
        )
        self.creer_eleve_actif(classe_externe, 'EXT-001')

        self.assertIsNone(trouver_classe_eleve(classe_note))

    def creer_utilisateur_ecole(self, ecole):
        utilisateur = User.objects.create_user(
            username=f'utilisateur-{ecole.id}',
            password='secret',
        )
        profil = utilisateur.profil
        profil.ecole = ecole
        profil.role = 'ADMIN'
        profil.is_validated = True
        profil.save()
        return utilisateur

    def creer_requete(self, classe_note, utilisateur):
        requete = RequestFactory().get(
            '/notes/eleves/',
            {'classe_id': classe_note.id},
        )
        SessionMiddleware(lambda request: None).process_request(requete)
        requete.session.save()
        requete.user = utilisateur
        return requete

    def test_vue_affiche_eleve_et_lien_vers_la_vraie_classe(self):
        classe_note = self.creer_classe_note()
        classe = Classe.objects.create(
            ecole=self.ecole,
            nom='Crèche',
            niveau='GARDERIE',
            annee_scolaire='2026-2027',
        )
        eleve = self.creer_eleve_actif(classe, 'CRE-003')
        requete = self.creer_requete(
            classe_note,
            self.creer_utilisateur_ecole(self.ecole),
        )

        reponse = gerer_eleves(requete)

        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, eleve.matricule)
        self.assertContains(reponse, f'?classe_id={classe.id}')

    def test_vue_refuse_classe_notes_d_un_autre_etablissement(self):
        classe_note_externe = self.creer_classe_note(self.autre_ecole)
        requete = self.creer_requete(
            classe_note_externe,
            self.creer_utilisateur_ecole(self.ecole),
        )

        with self.assertRaises(Http404):
            gerer_eleves(requete)
