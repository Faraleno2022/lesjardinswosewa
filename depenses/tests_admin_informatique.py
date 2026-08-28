from datetime import date
from decimal import Decimal
import time

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse

from eleves.models import Classe, Ecole, Eleve

from .admin import AbonnementInformatiqueAdmin
from .models_recouvrement import AbonnementInformatique


class AbonnementInformatiqueAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = get_user_model().objects.create_superuser(
            username='admin-informatique',
            email='admin-informatique@test.local',
            password='secret',
        )
        self.ecole = Ecole.objects.create(
            nom='Ecole informatique',
            adresse='Conakry',
            telephone='+224622001122',
            directeur='Direction',
            etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='CM1 informatique',
            niveau='PRIMAIRE_4',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='INFO-001',
            prenom='Aminata',
            nom='Diallo',
            sexe='F',
            classe=self.classe,
            statut='ACTIF',
        )
        self.abonnement = AbonnementInformatique.objects.create(
            ecole=self.ecole,
            eleve=self.eleve,
            date_debut=date(2026, 8, 1),
            date_fin=date(2027, 7, 31),
            montant=Decimal('250000'),
            cree_par=self.superuser,
        )
        self.client.force_login(self.superuser)
        session = self.client.session
        session['phone_verified'] = True
        session['phone_verified_at'] = time.time()
        session.save()

    def test_modele_est_enregistre_dans_administration(self):
        modele_admin = admin.site._registry.get(AbonnementInformatique)

        self.assertIsInstance(modele_admin, AbonnementInformatiqueAdmin)
        self.assertTrue(modele_admin.has_delete_permission(self._request()))
        self.assertIn('delete_selected', modele_admin.get_actions(self._request()))

    def test_superadministrateur_peut_supprimer_un_abonnement(self):
        response = self.client.post(
            reverse(
                'admin:depenses_abonnementinformatique_delete',
                args=[self.abonnement.pk],
            ),
            {'post': 'yes'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            AbonnementInformatique.objects.filter(pk=self.abonnement.pk).exists()
        )

    def _request(self):
        request = self.factory.get('/gestion-secrete-2026/depenses/abonnementinformatique/')
        request.user = self.superuser
        return request
