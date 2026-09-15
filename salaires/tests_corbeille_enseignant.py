import time
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from eleves.models import Classe, Ecole
from utilisateurs.models import JournalActivite

from .models import AffectationClasse, Enseignant, PresenceEnseignant, TypeEnseignant


class CorbeilleEnseignantTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username='admin-corbeille-enseignant',
            email='admin-corbeille-enseignant@test.local',
            password='secret',
        )
        self.ecole = Ecole.objects.create(
            nom='Ecole corbeille enseignant',
            adresse='Conakry',
            telephone='+224622004455',
            directeur='Direction',
            etat='VALIDE',
        )
        self.user.profil.ecole = self.ecole
        self.user.profil.save(update_fields=['ecole'])
        self.classe_a = Classe.objects.create(
            ecole=self.ecole,
            nom='Classe A corbeille',
            niveau='COLLEGE_7',
            annee_scolaire='2026-2027',
        )
        self.classe_b = Classe.objects.create(
            ecole=self.ecole,
            nom='Classe B corbeille',
            niveau='COLLEGE_8',
            annee_scolaire='2026-2027',
        )
        self.enseignant = Enseignant.objects.create(
            nom='LENO',
            prenoms='FARA',
            ecole=self.ecole,
            type_enseignant=TypeEnseignant.SECONDAIRE,
            statut='ACTIF',
            taux_horaire=Decimal('15000'),
            date_embauche=date(2025, 9, 1),
            cree_par=self.user,
        )
        for classe in (self.classe_a, self.classe_b):
            AffectationClasse.objects.create(
                enseignant=self.enseignant,
                classe=classe,
                heures_par_semaine=Decimal('8'),
                matiere='Informatique',
                date_debut=date(2025, 9, 1),
                actif=True,
            )
        PresenceEnseignant.objects.create(
            enseignant=self.enseignant,
            date=date(2026, 8, 25),
            statut='PRESENT',
            heures_travaillees=Decimal('8'),
            pointe_par=self.user,
        )
        self.client.force_login(self.user)
        session = self.client.session
        session['phone_verified'] = True
        session['phone_verified_at'] = time.time()
        session.save()

    def test_confirmation_ne_demande_plus_de_code(self):
        response = self.client.get(
            reverse('salaires:supprimer_enseignant', args=[self.enseignant.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Envoyer dans la corbeille')
        self.assertContains(response, 'Aucune donnée ne sera supprimée définitivement')
        self.assertNotContains(response, 'Code de vérification')
        self.assertNotContains(response, 'ACTION IRRÉVERSIBLE')

    def test_post_place_en_corbeille_et_conserve_relations(self):
        identifiant = self.enseignant.pk
        response = self.client.post(
            reverse('salaires:supprimer_enseignant', args=[identifiant]),
            {
                # Même un ancien formulaire ne peut plus forcer la suppression.
                'code_verification': '123456789',
                'suppression_definitive': 'on',
            },
        )

        self.assertRedirects(response, reverse('salaires:liste_enseignants'))
        enseignant = Enseignant.objects.get(pk=identifiant)
        self.assertEqual(enseignant.statut, 'DEMISSIONNAIRE')
        self.assertEqual(enseignant.affectations.count(), 2)
        self.assertEqual(enseignant.presences.count(), 1)
        self.assertTrue(
            JournalActivite.objects.filter(
                action='MISE_CORBEILLE',
                type_objet='ENSEIGNANT',
                objet_id=identifiant,
            ).exists()
        )

    def test_corbeille_est_separee_de_la_liste_normale(self):
        self.enseignant.statut = 'DEMISSIONNAIRE'
        self.enseignant.save(update_fields=['statut', 'date_modification'])

        liste = self.client.get(reverse('salaires:liste_enseignants'))
        corbeille = self.client.get(
            reverse('salaires:liste_enseignants'),
            {'statut': 'DEMISSIONNAIRE'},
        )

        self.assertNotIn(self.enseignant, liste.context['page_obj'].object_list)
        self.assertIn(self.enseignant, corbeille.context['page_obj'].object_list)
        self.assertContains(corbeille, 'Restaurer')

    def test_restauration_replace_enseignant_dans_liste_normale(self):
        self.enseignant.statut = 'DEMISSIONNAIRE'
        self.enseignant.save(update_fields=['statut', 'date_modification'])

        response = self.client.post(
            reverse(
                'salaires:changer_statut_enseignant',
                args=[self.enseignant.pk],
            ),
            {'nouveau_statut': 'ACTIF'},
        )

        self.assertRedirects(response, reverse('salaires:liste_enseignants'))
        self.enseignant.refresh_from_db()
        self.assertEqual(self.enseignant.statut, 'ACTIF')
        self.assertEqual(self.enseignant.affectations.count(), 2)
        self.assertEqual(self.enseignant.presences.count(), 1)
