from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from eleves.models import Ecole
from .models import Enseignant, PeriodeSalaire, TypeEnseignant
from .services import calculer_etat_salaire
from .tests import TEST_MIDDLEWARE


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class PersonnelPrimesTests(TestCase):
    types = ('CHAUFFEUR', 'VIGILE', 'ENTRETIEN', 'NOUNOU', 'RESTAURATION')

    def setUp(self):
        self.user = get_user_model().objects.create_superuser('personnel-tests', '', 'secret')
        self.ecole = Ecole.objects.create(nom='Personnel', adresse='Conakry',
            telephone='+224600000000', directeur='Direction', etat='VALIDE')
        self.user.profil.ecole = self.ecole
        self.user.profil.save(update_fields=['ecole'])
        self.periode = PeriodeSalaire.objects.create(ecole=self.ecole, mois=9,
            annee=2026, nombre_semaines=4, cree_par=self.user)
        self.client.force_login(self.user)

    def creer(self, type_personnel):
        response = self.client.post(reverse('salaires:ajouter_enseignant'), {
            'nom': type_personnel, 'prenoms': 'Test', 'ecole': self.ecole.pk,
            'type_enseignant': type_personnel, 'statut': 'ACTIF',
            'salaire_fixe': '1000000', 'date_embauche': '2026-09-01',
            'gestion_affectations_presente': '1',
        })
        self.assertEqual(response.status_code, 302)
        return Enseignant.objects.get(nom=type_personnel)

    def test_categories_creation_filtre_et_calcul_sans_classe(self):
        page = self.client.get(reverse('salaires:ajouter_enseignant'))
        for code in self.types:
            with self.subTest(type=code):
                self.assertContains(page, TypeEnseignant(code).label)
                travailleur = self.creer(code)
                self.assertTrue(travailleur.est_salaire_fixe)
                self.assertFalse(travailleur.est_taux_horaire)
                self.assertFalse(travailleur.affectations.exists())
                self.assertEqual(travailleur.calculer_salaire_mensuel(), Decimal('1000000'))
                etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
                self.assertEqual(etat.salaire_net, Decimal('1000000'))
                liste = self.client.get(reverse('salaires:liste_enseignants'), {'type_enseignant': code})
                self.assertEqual([e.pk for e in liste.context['enseignants']], [travailleur.pk])

    def test_primes_chaque_travailleur_recalcul_et_suppression(self):
        for code in self.types:
            with self.subTest(type=code):
                travailleur = self.creer(code)
                etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
                url = reverse('salaires:ajuster_etat_salaire', args=[etat.pk])
                detail = self.client.get(reverse('salaires:detail_enseignant', args=[travailleur.pk]))
                self.assertContains(detail, url + '#id_primes')
                data = {'salaire_base': '1000000', 'primes': '150000',
                        'deductions': '25000', 'observations': 'Prime de rendement'}
                self.assertEqual(self.client.post(url, data).status_code, 302)
                etat.refresh_from_db()
                self.assertEqual(etat.salaire_net, Decimal('1125000'))
                etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
                self.assertEqual(etat.primes, Decimal('150000'))
                self.assertEqual(etat.salaire_net, Decimal('1125000'))
                data['primes'] = '0'
                self.assertEqual(self.client.post(url, data).status_code, 302)
                etat.refresh_from_db()
                self.assertEqual(etat.salaire_net, Decimal('975000'))

    def test_prime_negative_refusee_et_salaire_valide_protege(self):
        travailleur = self.creer('CHAUFFEUR')
        etat, _ = calculer_etat_salaire(travailleur, self.periode, self.user)
        url = reverse('salaires:ajuster_etat_salaire', args=[etat.pk])
        data = {'salaire_base': '1000000', 'primes': '-10', 'deductions': '0'}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertIn('primes', response.context['form'].errors)
        etat.refresh_from_db()
        self.assertEqual(etat.primes, 0)
        etat.valide = True
        etat.save()
        data['primes'] = '150000'
        self.client.post(url, data)
        etat.refresh_from_db()
        self.assertEqual(etat.primes, 0)
