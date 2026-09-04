from datetime import date
from decimal import Decimal

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole

from .admin import AffectationClasseInline
from .forms import EnseignantForm
from .models import (
    AffectationClasse,
    Enseignant,
    TypeEnseignant,
)


INTEGRITY_MIDDLEWARE = 'ecole_moderne.integrity_middleware.IntegrityMiddleware'
TEST_MIDDLEWARE = tuple(
    middleware for middleware in settings.MIDDLEWARE
    if middleware != INTEGRITY_MIDDLEWARE
)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class AffectationsEnseignantsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin-affectations',
            email='admin-affectations@test.local',
            password='secret',
        )
        self.ecole = Ecole.objects.create(
            nom='École affectations',
            adresse='Conakry',
            telephone='+224610000001',
            directeur='Direction',
            etat='VALIDE',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='Autre école',
            adresse='Conakry',
            telephone='+224610000002',
            directeur='Autre direction',
            etat='VALIDE',
        )
        self.user.profil.ecole = self.ecole
        self.user.profil.save(update_fields=['ecole'])

        self.maternelle = self.creer_classe(
            'Grande section',
            'GRANDE_SECTION',
        )
        self.primaire_1 = self.creer_classe(
            'Première année',
            'PRIMAIRE_1',
        )
        self.primaire_2 = self.creer_classe(
            'Deuxième année',
            'PRIMAIRE_2',
        )
        self.college_7 = self.creer_classe(
            'Septième année',
            'COLLEGE_7',
        )
        self.college_8 = self.creer_classe(
            'Huitième année',
            'COLLEGE_8',
        )
        self.ancienne_secondaire = self.creer_classe(
            'Ancienne septième',
            'COLLEGE_7',
            annee='2025-2026',
        )
        self.classe_autre_ecole = self.creer_classe(
            'Classe externe',
            'COLLEGE_7',
            ecole=self.autre_ecole,
        )
        self.client.force_login(self.user)

    def creer_classe(self, nom, niveau, annee='2026-2027', ecole=None):
        return Classe.objects.create(
            ecole=ecole or self.ecole,
            nom=nom,
            niveau=niveau,
            annee_scolaire=annee,
        )

    def donnees_enseignant(self, type_enseignant, **supplements):
        donnees = {
            'nom': 'CAMARA',
            'prenoms': 'Aminata',
            'telephone': '',
            'adresse': 'Conakry',
            'ecole': str(self.ecole.pk),
            'type_enseignant': type_enseignant,
            'statut': 'ACTIF',
            'taux_horaire': (
                '15000'
                if type_enseignant == TypeEnseignant.SECONDAIRE
                else ''
            ),
            'salaire_fixe': (
                ''
                if type_enseignant == TypeEnseignant.SECONDAIRE
                else '1500000'
            ),
            'heures_mensuelles': '',
            'date_embauche': '2026-09-01',
            'gestion_affectations_presente': '1',
        }
        donnees.update(supplements)
        return donnees

    def enregistrer_formulaire(self, donnees, instance=None):
        form = EnseignantForm(
            data=donnees,
            instance=instance,
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        enseignant = form.save(commit=False)
        if not enseignant.cree_par_id:
            enseignant.cree_par = self.user
        enseignant.save()
        form.sauvegarder_affectations(enseignant)
        return enseignant

    def test_primaire_recoit_une_classe_principale(self):
        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.PRIMAIRE,
                classe_principale=str(self.primaire_1.pk),
            )
        )

        affectation = enseignant.affectations.get()
        self.assertEqual(affectation.classe, self.primaire_1)
        self.assertTrue(affectation.actif)
        self.assertIsNone(affectation.heures_par_semaine)

    def test_secondaire_recoit_plusieurs_affectations(self):
        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.SECONDAIRE,
                classes_secondaire=[
                    str(self.college_7.pk),
                    str(self.college_8.pk),
                ],
                matiere_affectation='Mathématiques',
                heures_affectation='8',
            )
        )

        affectations = enseignant.affectations.order_by('classe__nom')
        self.assertEqual(affectations.count(), 2)
        self.assertEqual(
            set(affectations.values_list('classe_id', flat=True)),
            {self.college_7.pk, self.college_8.pk},
        )
        self.assertTrue(
            all(
                item.matiere == 'Mathématiques'
                and item.heures_par_semaine == Decimal('8')
                for item in affectations
            )
        )

    def test_une_nouvelle_affectation_secondaire_exige_les_heures(self):
        form = EnseignantForm(
            data=self.donnees_enseignant(
                TypeEnseignant.SECONDAIRE,
                classes_secondaire=[str(self.college_7.pk)],
                heures_affectation='',
            ),
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('heures_affectation', form.errors)

    def test_classes_filtrees_par_ecole_cycle_et_annee(self):
        response = self.client.get(
            reverse('salaires:classes_disponibles_enseignant'),
            {
                'ecole_id': self.ecole.pk,
                'type_enseignant': TypeEnseignant.SECONDAIRE,
            },
        )

        self.assertEqual(response.status_code, 200)
        ids = {item['id'] for item in response.json()['classes']}
        self.assertEqual(ids, {self.college_7.pk, self.college_8.pk})
        self.assertNotIn(self.ancienne_secondaire.pk, ids)
        self.assertNotIn(self.classe_autre_ecole.pk, ids)
        self.assertNotIn(self.primaire_1.pk, ids)

    def test_changement_de_classe_conserve_l_historique(self):
        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.PRIMAIRE,
                classe_principale=str(self.primaire_1.pk),
            )
        )

        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.PRIMAIRE,
                classe_principale=str(self.primaire_2.pk),
            ),
            instance=enseignant,
        )

        self.assertEqual(enseignant.affectations.count(), 2)
        ancienne = enseignant.affectations.get(classe=self.primaire_1)
        nouvelle = enseignant.affectations.get(classe=self.primaire_2)
        self.assertFalse(ancienne.actif)
        self.assertIsNotNone(ancienne.date_fin)
        self.assertTrue(nouvelle.actif)

    def test_changement_de_cycle_cloture_l_ancienne_classe(self):
        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.PRIMAIRE,
                classe_principale=str(self.primaire_1.pk),
            )
        )

        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.SECONDAIRE,
                classes_secondaire=[str(self.college_7.pk)],
                heures_affectation='6',
            ),
            instance=enseignant,
        )

        ancienne = enseignant.affectations.get(classe=self.primaire_1)
        nouvelle = enseignant.affectations.get(classe=self.college_7)
        self.assertFalse(ancienne.actif)
        self.assertIsNotNone(ancienne.date_fin)
        self.assertTrue(nouvelle.actif)
        self.assertEqual(nouvelle.heures_par_semaine, Decimal('6'))

    def test_ancien_formulaire_ne_cloture_pas_les_affectations(self):
        enseignant = self.enregistrer_formulaire(
            self.donnees_enseignant(
                TypeEnseignant.PRIMAIRE,
                classe_principale=str(self.primaire_1.pk),
            )
        )
        donnees = self.donnees_enseignant(TypeEnseignant.PRIMAIRE)
        donnees.pop('gestion_affectations_presente')

        self.enregistrer_formulaire(donnees, instance=enseignant)

        affectation = enseignant.affectations.get()
        self.assertTrue(affectation.actif)
        self.assertIsNone(affectation.date_fin)

    def test_modele_refuse_une_classe_d_un_cycle_incompatible(self):
        enseignant = Enseignant.objects.create(
            nom='DIALLO',
            prenoms='Mamadou',
            ecole=self.ecole,
            type_enseignant=TypeEnseignant.PRIMAIRE,
            statut='ACTIF',
            salaire_fixe=Decimal('1200000'),
            date_embauche=date(2026, 9, 1),
            cree_par=self.user,
        )

        with self.assertRaises(ValidationError):
            AffectationClasse.objects.create(
                enseignant=enseignant,
                classe=self.college_7,
                date_debut=date(2026, 9, 1),
                actif=True,
            )

    def test_vue_ajout_enregistre_aussi_la_classe(self):
        response = self.client.post(
            reverse('salaires:ajouter_enseignant'),
            self.donnees_enseignant(
                TypeEnseignant.MATERNELLE,
                classe_principale=str(self.maternelle.pk),
            ),
        )

        enseignant = Enseignant.objects.get(nom='CAMARA')
        self.assertRedirects(
            response,
            reverse('salaires:detail_enseignant', args=[enseignant.pk]),
        )
        self.assertTrue(
            enseignant.affectations.filter(
                classe=self.maternelle,
                actif=True,
            ).exists()
        )

    def test_administration_expose_les_affectations_sans_suppression(self):
        enseignant_admin = admin.site._registry[Enseignant]
        affectation_admin = admin.site._registry[AffectationClasse]

        self.assertIn(AffectationClasseInline, enseignant_admin.inlines)
        self.assertFalse(enseignant_admin.has_delete_permission(None))
        self.assertFalse(affectation_admin.has_delete_permission(None))
