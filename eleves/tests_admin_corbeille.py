from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from synchronisation.models import SyncChange

from .admin import EleveAdmin, EleveCorbeilleAdmin
from .models import Classe, Ecole, Eleve, EleveCorbeille


class EleveCorbeilleAdminTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.superuser = User.objects.create_superuser(
            'super-corbeille', 'super-corbeille@test.local', 'secret'
        )
        self.staff = User.objects.create_user(
            'staff-corbeille', 'staff-corbeille@test.local', 'secret',
            is_staff=True,
        )
        self.ecole = Ecole.objects.create(
            nom='Ecole corbeille admin',
            adresse='Conakry',
            telephone='+224622009900',
            directeur='Direction',
            etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='Classe corbeille',
            niveau='PRIMAIRE_1',
            code_matricule='COR',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='COR-001',
            prenom='Aminata',
            nom='Diallo',
            sexe='F',
            classe=self.classe,
            statut='ACTIF',
        )
        self.eleve.placer_dans_corbeille(self.superuser)
        self.admin_corbeille = EleveCorbeilleAdmin(EleveCorbeille, admin.site)

    def _request(self, user):
        request = self.factory.get('/admin/eleves/elevecorbeille/')
        request.user = user
        return request

    def test_superadministrateur_peut_supprimer_definitivement(self):
        request = self._request(self.superuser)
        eleve_corbeille = EleveCorbeille.objects.get(pk=self.eleve.pk)

        self.assertTrue(
            self.admin_corbeille.has_delete_permission(request, eleve_corbeille)
        )
        self.assertIn(
            'supprimer_definitivement',
            self.admin_corbeille.get_actions(request),
        )
        self.assertNotIn('delete_selected', self.admin_corbeille.get_actions(request))

    def test_administrateur_avec_permission_peut_supprimer(self):
        self.staff.profil.peut_supprimer_eleves_definitivement = True
        self.staff.profil.save(
            update_fields=['peut_supprimer_eleves_definitivement']
        )
        request = self._request(self.staff)

        self.assertTrue(self.admin_corbeille.has_delete_permission(request))
        self.assertIn(
            'supprimer_definitivement',
            self.admin_corbeille.get_actions(request),
        )

    def test_administrateur_sans_permission_ne_peut_pas_supprimer(self):
        request = self._request(self.staff)

        self.assertFalse(self.admin_corbeille.has_delete_permission(request))
        self.assertNotIn(
            'supprimer_definitivement',
            self.admin_corbeille.get_actions(request),
        )
        with self.assertRaises(PermissionDenied):
            self.admin_corbeille.delete_queryset(
                request,
                EleveCorbeille.objects.filter(pk=self.eleve.pk),
            )

    def test_suppression_django_admin_est_definitive_et_synchronisee(self):
        sync_uuid = self.eleve.sync_uuid
        SyncChange.objects.all().delete()
        self.client.force_login(self.superuser)

        response = self.client.post(
            reverse(
                'admin:eleves_elevecorbeille_delete',
                args=[self.eleve.pk],
            ),
            {'post': 'yes'},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Eleve.objects.filter(pk=self.eleve.pk).exists())
        self.assertTrue(
            SyncChange.objects.filter(
                model_label='eleves.Eleve',
                object_uuid=sync_uuid,
                operation=SyncChange.OPERATION_DELETE,
            ).exists()
        )

    def test_suppression_depuis_liste_normale_reste_une_mise_en_corbeille(self):
        eleve = Eleve.objects.create(
            matricule='COR-002',
            prenom='Mamadou',
            nom='Bah',
            sexe='M',
            classe=self.classe,
            statut='ACTIF',
        )
        admin_eleve = EleveAdmin(Eleve, admin.site)

        admin_eleve.delete_model(self._request(self.superuser), eleve)

        eleve.refresh_from_db()
        self.assertTrue(eleve.est_dans_corbeille)
