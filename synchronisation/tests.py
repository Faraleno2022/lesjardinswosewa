import json
import os
import secrets
import shutil
import tempfile
import uuid
from unittest import mock
from urllib.error import HTTPError, URLError

from django.contrib.auth.models import Permission, User
from decimal import Decimal
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from eleves.models import Classe, Ecole
from utilisateurs.models import Profil

from . import auto_sync
from .auto_sync import (
    MAX_APPLY_ATTEMPTS,
    MAX_PUSH_ATTEMPTS,
    MAX_PUSH_BYTES,
    _retry_failed,
)
from .engine import (
    FILES_PAYLOAD_KEY,
    MAX_SYNC_FILE_BYTES,
    apply_sync_change,
    deserialize_field,
    serialize_instance,
)
from .models import SyncChange, SyncDevice
from .mixins import SyncTrackedModel
from .registry import SYNC_MODEL_SET


class EcoleOfflineAdminTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='superoffline', password='secret123', email='admin@example.com',
        )
        self.ecole = Ecole.objects.create(
            nom='Ecole Offline',
            adresse='Conakry',
            telephone='+224600000001',
            directeur='Direction',
            etat='VALIDE',
        )
        self.client.force_login(self.superuser)
        self.url = reverse(
            'admin:eleves_ecole_version_hors_ligne', args=[self.ecole.pk],
        )

    def test_bouton_et_page_sont_disponibles_depuis_administration(self):
        changelist = self.client.get(reverse('admin:eleves_ecole_changelist'))
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, self.url)
        self.assertContains(changelist, 'Configurer la version hors ligne')

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.ecole.nom)
        self.assertContains(response, 'Créer et télécharger la configuration')

    @override_settings(MYSCHOOL_SYNC_PUBLIC_URL='https://ecole.example.com')
    def test_creation_telecharge_une_configuration_secrete_propre_ecole(self):
        response = self.client.post(self.url, {
            'action': 'creer',
            'nom': 'Poste comptabilité',
            'intervalle': '90',
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Disposition'],
            'attachment; filename="sync_config.json"',
        )
        self.assertIn('no-store', response['Cache-Control'])
        configuration = json.loads(response.content.decode('utf-8'))
        self.assertEqual(
            configuration['MYSCHOOL_SYNC_SERVER_URL'],
            'https://ecole.example.com',
        )
        self.assertEqual(configuration['MYSCHOOL_SYNC_ECOLE_ID'], self.ecole.pk)
        self.assertEqual(configuration['MYSCHOOL_SYNC_INTERVAL'], 90)

        device = SyncDevice.objects.get(ecole=self.ecole)
        self.assertEqual(device.nom, 'Poste comptabilité')
        self.assertEqual(str(device.device_id), configuration['MYSCHOOL_SYNC_DEVICE_ID'])
        self.assertNotEqual(device.token_hash, configuration['MYSCHOOL_SYNC_TOKEN'])
        self.assertTrue(device.verifier_token(configuration['MYSCHOOL_SYNC_TOKEN']))

    def test_revoquer_un_poste_le_bloque_sans_le_supprimer(self):
        device = SyncDevice(ecole=self.ecole, nom='Poste direction')
        device.definir_token('jeton-secret')
        device.save()

        response = self.client.post(self.url, {
            'action': 'revoquer',
            'device_id': str(device.pk),
        })

        self.assertRedirects(response, self.url)
        device.refresh_from_db()
        self.assertFalse(device.actif)
        self.assertFalse(device.verifier_token('mauvais-jeton'))

    def test_admin_ecole_ne_peut_pas_configurer_une_autre_ecole(self):
        autre_ecole = Ecole.objects.create(
            nom='Autre Ecole',
            adresse='Conakry',
            telephone='+224600000002',
            directeur='Direction',
            etat='VALIDE',
        )
        admin_ecole = User.objects.create_user(
            username='adminoffline', password='secret123', is_staff=True,
        )
        profil, _ = Profil.objects.get_or_create(user=admin_ecole)
        profil.role = 'ADMIN'
        profil.ecole = self.ecole
        profil.save(update_fields=['role', 'ecole'])
        admin_ecole.user_permissions.add(Permission.objects.get(codename='change_ecole'))
        self.client.force_login(admin_ecole)

        response = self.client.get(reverse(
            'admin:eleves_ecole_version_hors_ligne', args=[autre_ecole.pk],
        ))

        self.assertEqual(response.status_code, 403)
        self.assertFalse(SyncDevice.objects.filter(ecole=autre_ecole).exists())


class SynchronisationApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='adminsync', password='secret123')
        self.ecole = Ecole.objects.create(
            nom='Ecole Test',
            adresse='Conakry',
            telephone='+224600000000',
            directeur='Direction',
            etat='VALIDE',
        )
        profil, _ = Profil.objects.get_or_create(user=self.user)
        profil.role = 'ADMIN'
        profil.ecole = self.ecole
        profil.save(update_fields=['role', 'ecole'])
        self.client = Client()

    def test_health_endpoint(self):
        response = self.client.get(reverse('synchronisation:health'))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])


    def test_register_device_and_push_change(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('synchronisation:register_device'),
            data=json.dumps({'nom': 'Poste direction'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()

        response = self.client.post(
            reverse('synchronisation:push'),
            data=json.dumps({
                'changes': [
                    {
                        'model': 'eleves.Ecole',
                        'object_uuid': str(self.ecole.sync_uuid),
                        'operation': 'UPDATE',
                        'payload': {
                            'sync_uuid': str(self.ecole.sync_uuid),
                            'nom': 'Ecole Test Sync',
                            'adresse': 'Conakry',
                            'telephone': '+224600000000',
                            'directeur': 'Direction',
                            'etat': 'VALIDE',
                        },
                    }
                ]
            }),
            content_type='application/json',
            HTTP_X_SYNC_DEVICE=data['device_id'],
            HTTP_X_SYNC_TOKEN=data['sync_token'],
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['accepted_count'], 1)

    def test_register_device_with_admin_token_and_pull_other_device_changes(self):
        from django.test import override_settings

        with override_settings(MYSCHOOL_SYNC_ADMIN_TOKEN='bootstrap-secret'):
            response = self.client.post(
                reverse('synchronisation:register_device'),
                data=json.dumps({'nom': 'Poste 1', 'ecole_id': self.ecole.id}),
                content_type='application/json',
                HTTP_X_SYNC_ADMIN_TOKEN='bootstrap-secret',
            )
        self.assertEqual(response.status_code, 201)
        device_one = response.json()

        with override_settings(MYSCHOOL_SYNC_ADMIN_TOKEN='bootstrap-secret'):
            response = self.client.post(
                reverse('synchronisation:register_device'),
                data=json.dumps({'nom': 'Poste 2', 'ecole_id': self.ecole.id}),
                content_type='application/json',
                HTTP_X_SYNC_ADMIN_TOKEN='bootstrap-secret',
            )
        self.assertEqual(response.status_code, 201)
        device_two = response.json()

        response = self.client.post(
            reverse('synchronisation:push'),
            data=json.dumps({
                'changes': [
                    {
                        'model': 'eleves.Ecole',
                        'object_uuid': str(self.ecole.sync_uuid),
                        'operation': 'UPDATE',
                        'payload': {
                            'sync_uuid': str(self.ecole.sync_uuid),
                            'nom': 'Ecole Test Poste 1',
                            'adresse': 'Conakry',
                            'telephone': '+224600000000',
                            'directeur': 'Direction',
                            'etat': 'VALIDE',
                        },
                    }
                ]
            }),
            content_type='application/json',
            HTTP_X_SYNC_DEVICE=device_one['device_id'],
            HTTP_X_SYNC_TOKEN=device_one['sync_token'],
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.get(
            reverse('synchronisation:pull'),
            HTTP_X_SYNC_DEVICE=device_two['device_id'],
            HTTP_X_SYNC_TOKEN=device_two['sync_token'],
        )
        self.assertEqual(response.status_code, 200)
        # La creation de l'ecole (nee sur le serveur) et l'envoi du poste 1 :
        # les deux origines sont livrees au poste 2.
        recus = response.json()['changes']
        self.assertEqual(len(recus), 2)
        self.assertEqual({item['model_label'] for item in recus}, {'eleves.Ecole'})


class SynchronisationConfigurationTests(TestCase):
    def test_les_decimaux_json_sont_reconvertis_avant_sauvegarde(self):
        from depenses.models import Depense

        field = Depense._meta.get_field('montant_ht')
        self.assertEqual(deserialize_field(field, '125000'), Decimal('125000'))

    def test_un_utilisateur_obligatoire_utilise_admin_local(self):
        from salaires.models import Enseignant

        admin = User.objects.create_superuser('adminlocal', '', 'secret')
        field = Enseignant._meta.get_field('cree_par')
        self.assertEqual(deserialize_field(field, None), admin)

    def test_tous_les_modeles_suivis_sont_dans_le_registre(self):
        from django.apps import apps

        manquants = sorted(
            f'{model._meta.app_label}.{model.__name__}'
            for model in apps.get_models()
            if issubclass(model, SyncTrackedModel)
            and not model._meta.abstract
            and not model._meta.proxy
            and f'{model._meta.app_label}.{model.__name__}' not in SYNC_MODEL_SET
        )
        self.assertEqual(manquants, [])

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://ecole.example',
        MYSCHOOL_SYNC_DEVICE_ID='11111111-1111-1111-1111-111111111111',
        MYSCHOOL_SYNC_TOKEN='token-client',
        MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_poste_neuf_amorce_ecole_depuis_snapshot_initial(self):
        school_uuid = uuid.uuid4()
        response = {
            'ok': True,
            'ecole_id': 1,
            'initial': True,
            'latest_change_id': None,
            'changes': [{
                'id': None,
                'model': 'eleves.Ecole',
                'model_label': 'eleves.Ecole',
                'object_uuid': str(school_uuid),
                'operation': 'UPDATE',
                'payload': {
                    'sync_uuid': str(school_uuid),
                    'nom': 'Les Jardins Wosewa',
                    'adresse': 'Conakry',
                    'telephone': '+224600000099',
                    'directeur': 'Direction',
                    'etat': 'VALIDE',
                },
            }],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, '.sync_state.json')
            with mock.patch.object(auto_sync, '_state_path', return_value=state_path), mock.patch.object(
                auto_sync, '_request_json', return_value=response,
            ) as request_json:
                self.assertTrue(auto_sync._run_once())

            self.assertIn('initial=1', request_json.call_args.args[0])
            with open(state_path, encoding='utf-8') as state_file:
                self.assertTrue(json.load(state_file)['initial_done'])

        ecole = Ecole.objects.get(pk=1)
        self.assertEqual(ecole.sync_uuid, school_uuid)
        self.assertEqual(ecole.nom.upper(), 'LES JARDINS WOSEWA')

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://ecole.example',
        MYSCHOOL_SYNC_DEVICE_ID='11111111-1111-1111-1111-111111111111',
        MYSCHOOL_SYNC_TOKEN='token-client',
        MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_base_existante_sans_etat_recoit_aussi_snapshot_initial(self):
        ancienne_uuid = uuid.uuid4()
        school_uuid = uuid.uuid4()
        ecole_locale = Ecole.objects.create(
            pk=1,
            sync_uuid=ancienne_uuid,
            nom='Ancienne fiche locale',
            adresse='Conakry',
            telephone='+224600000000',
            directeur='Direction',
            etat='VALIDE',
        )
        classe_uuid = uuid.uuid4()
        response = {
            'ok': True,
            'ecole_id': 1,
            'initial': True,
            'latest_change_id': None,
            'changes': [
                {
                    'id': None,
                    'model': 'eleves.Ecole',
                    'model_label': 'eleves.Ecole',
                    'object_uuid': str(school_uuid),
                    'operation': 'UPDATE',
                    'payload': {
                        'sync_uuid': str(school_uuid),
                        'nom': 'Les Jardins Wosewa',
                        'adresse': 'Conakry',
                        'telephone': '+224600000099',
                        'directeur': 'Direction',
                        'etat': 'VALIDE',
                    },
                },
                {
                    'id': None,
                    'model': 'eleves.Classe',
                    'model_label': 'eleves.Classe',
                    'object_uuid': str(classe_uuid),
                    'operation': 'UPDATE',
                    'payload': {
                        'sync_uuid': str(classe_uuid),
                        'ecole': {
                            'model': 'eleves.Ecole',
                            'sync_uuid': str(school_uuid),
                            'pk': 1,
                        },
                        'nom': '1ere annee',
                        'niveau': 'PRIMAIRE_1',
                        'annee_scolaire': '2026-2027',
                        'capacite_max': 35,
                    },
                },
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, '.sync_state.json')
            with mock.patch.object(auto_sync, '_state_path', return_value=state_path), mock.patch.object(
                auto_sync, '_request_json', return_value=response,
            ) as request_json:
                self.assertTrue(auto_sync._run_once())

            self.assertIn('initial=1', request_json.call_args.args[0])
            with open(state_path, encoding='utf-8') as state_file:
                state = json.load(state_file)
            self.assertTrue(state['initial_done'])
            self.assertEqual(state['school_sync_uuid'], str(school_uuid))

        ecole_locale.refresh_from_db()
        self.assertEqual(ecole_locale.sync_uuid, school_uuid)
        self.assertEqual(ecole_locale.nom.upper(), 'LES JARDINS WOSEWA')
        self.assertTrue(ecole_locale.classes.filter(sync_uuid=classe_uuid).exists())

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://ecole.example',
        MYSCHOOL_SYNC_DEVICE_ID='11111111-1111-1111-1111-111111111111',
        MYSCHOOL_SYNC_TOKEN='token-client',
        MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_base_initialisee_utilise_ensuite_le_pull_incremental(self):
        ecole = Ecole.objects.create(
            pk=1,
            nom='Les Jardins Wosewa',
            adresse='Conakry',
            telephone='+224600000099',
            directeur='Direction',
            etat='VALIDE',
        )
        response = {
            'ok': True,
            'ecole_id': 1,
            'latest_change_id': None,
            'changes': [],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            state_path = os.path.join(temp_dir, '.sync_state.json')
            with open(state_path, 'w', encoding='utf-8') as state_file:
                json.dump({
                    'initial_done': True,
                    'school_sync_uuid': str(ecole.sync_uuid),
                }, state_file)
            with mock.patch.object(auto_sync, '_state_path', return_value=state_path), mock.patch.object(
                auto_sync, '_request_json', return_value=response,
            ) as request_json:
                self.assertTrue(auto_sync._run_once())

        self.assertNotIn('initial=1', request_json.call_args.args[0])


class SynchronisationRenvoiPushTests(TestCase):
    """Un renvoi du meme changement ne doit pas empiler de lignes cote serveur."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Renvoi',
            adresse='Conakry',
            telephone='+224600000005',
            directeur='Direction',
            etat='VALIDE',
        )
        self.client = Client()
        with override_settings(MYSCHOOL_SYNC_ADMIN_TOKEN='bootstrap-secret'):
            response = self.client.post(
                reverse('synchronisation:register_device'),
                data=json.dumps({'nom': 'Poste', 'ecole_id': self.ecole.id}),
                content_type='application/json',
                HTTP_X_SYNC_ADMIN_TOKEN='bootstrap-secret',
            )
        self.device = response.json()
        SyncChange.objects.filter(ecole=self.ecole).delete()

    def _push(self, change):
        return self.client.post(
            reverse('synchronisation:push'),
            data=json.dumps({'changes': [change]}),
            content_type='application/json',
            HTTP_X_SYNC_DEVICE=self.device['device_id'],
            HTTP_X_SYNC_TOKEN=self.device['sync_token'],
        )

    def _changement_refuse(self):
        """Classe dont l'ecole est introuvable cote serveur : refus garanti."""
        return {
            'model': 'eleves.Classe',
            'object_uuid': str(uuid.uuid4()),
            'operation': 'CREATE',
            'client_change_id': 12,
            'payload': {
                'ecole': {'model': 'eleves.Ecole', 'sync_uuid': str(uuid.uuid4()), 'pk': None},
                'nom': 'CE1 B',
                'niveau': 'CE1',
                'annee_scolaire': '2025-2026',
                'capacite_max': 40,
            },
        }

    def test_un_refus_renvoye_n_empile_pas_de_lignes(self):
        change = self._changement_refuse()
        for _ in range(3):
            self.assertEqual(self._push(change).json()['rejected_count'], 1)

        lignes = SyncChange.objects.filter(ecole=self.ecole)
        self.assertEqual(lignes.count(), 1)  # une seule ligne, pas trois
        self.assertEqual(lignes.first().tentatives, 3)

    def test_un_renvoi_accepte_est_servi_aux_autres_postes(self):
        """La ligne recreee doit passer apres le curseur des postes a jour."""
        change = self._changement_refuse()
        self.assertEqual(self._push(change).json()['rejected_count'], 1)
        curseur = SyncChange.objects.get(ecole=self.ecole).id

        # La dependance arrive, le renvoi est accepte.
        Ecole.objects.create(
            nom='Ecole Attendue',
            adresse='Kindia',
            telephone='+224600000006',
            directeur='Direction',
            etat='VALIDE',
            sync_uuid=change['payload']['ecole']['sync_uuid'],
        )
        self.assertEqual(self._push(change).json()['accepted_count'], 1)

        applique = SyncChange.objects.get(ecole=self.ecole, statut=SyncChange.STATUT_APPLIED)
        self.assertGreater(applique.id, curseur)

    def test_un_changement_deja_applique_est_reconnu_sans_etre_rejoue(self):
        change = {
            'model': 'eleves.Ecole',
            'object_uuid': str(self.ecole.sync_uuid),
            'operation': 'UPDATE',
            'client_change_id': 7,
            'payload': {
                'sync_uuid': str(self.ecole.sync_uuid),
                'nom': 'Ecole Renvoi Sync',
                'adresse': 'Conakry',
                'telephone': '+224600000005',
                'directeur': 'Direction',
                'etat': 'VALIDE',
            },
        }
        self.assertEqual(self._push(change).json()['accepted_count'], 1)

        # Accuse de reception perdu : le poste renvoie le meme changement.
        data = self._push(change).json()
        self.assertEqual(data['accepted_count'], 1)
        self.assertEqual(data['already_applied_count'], 1)
        self.assertEqual(SyncChange.objects.filter(ecole=self.ecole).count(), 1)

    def test_un_poste_sans_identifiant_conserve_l_ancien_comportement(self):
        change = self._changement_refuse()
        change.pop('client_change_id')
        for _ in range(2):
            self._push(change)

        self.assertEqual(SyncChange.objects.filter(ecole=self.ecole).count(), 2)


class SynchronisationFichiersTests(TestCase):
    """Le contenu des fichiers doit traverser la synchronisation, pas juste le chemin."""

    def setUp(self):
        media = tempfile.mkdtemp(prefix='sync-media-')
        override = override_settings(MEDIA_ROOT=media)
        override.enable()
        self.addCleanup(shutil.rmtree, media, True)
        self.addCleanup(override.disable)

        self.ecole = Ecole.objects.create(
            nom='Ecole Medias',
            adresse='Conakry',
            telephone='+224600000001',
            directeur='Direction',
            etat='VALIDE',
        )
        self.contenu = b'\x89PNG\r\n\x1a\n' + b'logo-binaire' * 20
        self.ecole.logo = SimpleUploadedFile('logo.png', self.contenu, content_type='image/png')
        self.ecole.save()
        self.addCleanup(self.ecole.logo.close)

    def test_serialisation_embarque_le_contenu_du_fichier(self):
        payload = serialize_instance(self.ecole)
        self.assertEqual(payload['logo'], self.ecole.logo.name)
        fichier = payload[FILES_PAYLOAD_KEY]['logo']
        self.assertEqual(fichier['name'], self.ecole.logo.name)
        self.assertEqual(fichier['size'], len(self.contenu))

    def test_le_fichier_reste_lisible_apres_serialisation(self):
        """La lecture pour la synchro ne doit pas fermer le fichier de l'appelant."""
        serialize_instance(self.ecole)
        self.assertEqual(self.ecole.logo.read(), self.contenu)

    def test_fichier_trop_volumineux_ne_transporte_que_son_chemin(self):
        volumineux = b'0' * (MAX_SYNC_FILE_BYTES + 1)
        self.ecole.image = SimpleUploadedFile('grande.png', volumineux, content_type='image/png')
        self.ecole.save()

        payload = serialize_instance(self.ecole)
        self.assertEqual(payload['image'], self.ecole.image.name)
        self.assertNotIn('image', payload[FILES_PAYLOAD_KEY])

    def test_snapshot_initial_exclut_le_contenu_des_fichiers(self):
        payload = serialize_instance(self.ecole, include_files=False)
        self.assertEqual(payload['logo'], self.ecole.logo.name)
        self.assertNotIn(FILES_PAYLOAD_KEY, payload)

    def test_application_restaure_le_fichier_absent(self):
        payload = serialize_instance(self.ecole)
        nom_fichier = self.ecole.logo.name
        default_storage.delete(nom_fichier)
        self.assertFalse(default_storage.exists(nom_fichier))

        change = SyncChange.objects.create(
            ecole=self.ecole,
            model_label='eleves.Ecole',
            object_uuid=self.ecole.sync_uuid,
            operation=SyncChange.OPERATION_UPDATE,
            payload=payload,
        )
        apply_sync_change(change)

        self.assertTrue(default_storage.exists(nom_fichier))
        with default_storage.open(nom_fichier, 'rb') as handle:
            self.assertEqual(handle.read(), self.contenu)


class SynchronisationRepriseEchecsTests(TestCase):
    """Un changement recu en echec doit etre rejoue, pas perdu."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Reprise',
            adresse='Conakry',
            telephone='+224600000002',
            directeur='Direction',
            etat='VALIDE',
        )
        self.uuid_ecole_absente = uuid.uuid4()

    def _changement_classe_orpheline(self):
        """Une classe dont l'ecole n'est pas encore arrivee sur ce poste."""
        return SyncChange.objects.create(
            ecole=self.ecole,
            model_label='eleves.Classe',
            object_uuid=uuid.uuid4(),
            operation=SyncChange.OPERATION_CREATE,
            payload={
                'ecole': {
                    'model': 'eleves.Ecole',
                    'sync_uuid': str(self.uuid_ecole_absente),
                    'pk': None,
                    'text': 'Ecole distante',
                },
                'nom': 'CM2 A',
                'niveau': 'CM2',
                'annee_scolaire': '2025-2026',
                'capacite_max': 40,
            },
        )

    def test_echec_rejoue_des_que_la_dependance_arrive(self):
        change = self._changement_classe_orpheline()
        with self.assertRaises(ValueError):
            apply_sync_change(change)
        change.statut = SyncChange.STATUT_FAILED
        change.save(update_fields=['statut'])

        # Tant que l'ecole manque, la reprise echoue et compte les tentatives.
        self.assertEqual(_retry_failed(self.ecole), 0)
        change.refresh_from_db()
        self.assertEqual(change.tentatives, 1)
        self.assertEqual(change.statut, SyncChange.STATUT_FAILED)

        # L'ecole arrive : le changement est enfin applique.
        Ecole.objects.create(
            nom='Ecole Distante',
            adresse='Kindia',
            telephone='+224600000003',
            directeur='Direction',
            etat='VALIDE',
            sync_uuid=self.uuid_ecole_absente,
        )
        self.assertEqual(_retry_failed(self.ecole), 1)
        change.refresh_from_db()
        self.assertEqual(change.statut, SyncChange.STATUT_APPLIED)
        self.assertTrue(Classe.objects.filter(sync_uuid=change.object_uuid).exists())

    def test_abandon_apres_le_nombre_maximal_de_tentatives(self):
        change = self._changement_classe_orpheline()
        change.statut = SyncChange.STATUT_FAILED
        change.save(update_fields=['statut'])

        for _ in range(MAX_APPLY_ATTEMPTS):
            _retry_failed(self.ecole)

        change.refresh_from_db()
        self.assertEqual(change.statut, SyncChange.STATUT_ABANDONED)
        self.assertEqual(change.tentatives, MAX_APPLY_ATTEMPTS)

        # Abandonne : plus jamais rejoue, le compteur ne bouge plus.
        self.assertEqual(_retry_failed(self.ecole), 0)
        change.refresh_from_db()
        self.assertEqual(change.tentatives, MAX_APPLY_ATTEMPTS)


class SynchronisationLotPousseTests(TestCase):
    """Le lot pousse doit rester sous la limite de taille du serveur."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Lot',
            adresse='Conakry',
            telephone='+224600000004',
            directeur='Direction',
            etat='VALIDE',
        )
        SyncChange.objects.filter(ecole=self.ecole).delete()

    def _creer_changements_volumineux(self, nombre):
        gros_contenu = 'x' * (MAX_PUSH_BYTES // 3)
        for index in range(nombre):
            SyncChange.objects.create(
                ecole=self.ecole,
                model_label='eleves.Ecole',
                object_uuid=uuid.uuid4(),
                operation=SyncChange.OPERATION_UPDATE,
                payload={'nom': f'Ecole {index}', FILES_PAYLOAD_KEY: {
                    'logo': {'name': 'l.png', 'size': 1, 'content_b64': gros_contenu},
                }},
            )

    def test_le_lot_est_borne_par_la_taille_et_le_reste_suit(self):
        self._creer_changements_volumineux(8)
        envoyes = []

        def _faux_request(url, device_id, token, payload=None, **kwargs):
            envoyes.append(payload['changes'])
            return {
                'ok': True,
                'accepted': [{'index': i} for i in range(len(payload['changes']))],
            }

        with mock.patch.object(auto_sync, '_request_json', _faux_request):
            premier = auto_sync._push('https://serveur', 'device', 'token', self.ecole)
            second = auto_sync._push('https://serveur', 'device', 'token', self.ecole)

        self.assertLess(len(envoyes[0]), 8)  # lot tronque, pas les 8 d'un coup
        self.assertEqual(premier, len(envoyes[0]))
        self.assertEqual(second, len(envoyes[1]))
        self.assertEqual(
            SyncChange.objects.filter(
                ecole=self.ecole, statut=SyncChange.STATUT_PENDING,
            ).count(),
            8 - premier - second,
        )

    def _refus_systematique(self, envois=None):
        def _faux_request(url, device_id, token, payload=None, **kwargs):
            if envois is not None:
                envois.append(payload['changes'])
            return {
                'ok': True,
                'accepted': [],
                'rejected': [{'index': 0, 'error': 'Relation introuvable pour ecole.'}],
            }
        return _faux_request

    def _changement_local(self):
        return SyncChange.objects.create(
            ecole=self.ecole,
            model_label='eleves.Classe',
            object_uuid=uuid.uuid4(),
            operation=SyncChange.OPERATION_CREATE,
            payload={'nom': 'CP A'},
        )

    def test_un_refus_serveur_reste_en_attente_avec_sa_cause(self):
        self._changement_local()

        with mock.patch.object(auto_sync, '_request_json', self._refus_systematique()):
            self.assertEqual(auto_sync._push('https://serveur', 'device', 'token', self.ecole), 0)

        change = SyncChange.objects.filter(ecole=self.ecole).first()
        self.assertEqual(change.statut, SyncChange.STATUT_PENDING)  # sera renvoye
        self.assertEqual(change.tentatives, 1)
        self.assertIn('Relation introuvable', change.erreur)

    def test_un_refus_persistant_cesse_d_etre_renvoye(self):
        change = self._changement_local()
        envois = []

        with mock.patch.object(auto_sync, '_request_json', self._refus_systematique(envois)):
            for _ in range(MAX_PUSH_ATTEMPTS + 3):
                auto_sync._push('https://serveur', 'device', 'token', self.ecole)

        change.refresh_from_db()
        self.assertEqual(change.statut, SyncChange.STATUT_ABANDONED)
        self.assertEqual(change.tentatives, MAX_PUSH_ATTEMPTS)
        # Le serveur n'a plus ete sollicite une fois la limite atteinte.
        self.assertEqual(len(envois), MAX_PUSH_ATTEMPTS)

    def test_le_lot_porte_l_identifiant_local_du_changement(self):
        change = self._changement_local()
        envois = []

        with mock.patch.object(auto_sync, '_request_json', self._refus_systematique(envois)):
            auto_sync._push('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(envois[0][0]['client_change_id'], change.id)


class PropagationImmediateTests(TestCase):
    """
    Ce qui fait qu'un ajout apparait tout de suite sur les autres postes.

    Trois maillons sont couverts ici : la saisie reveille l'envoi sans
    attendre le cycle, le serveur distribue aussi ce qui nait chez lui, et le
    poste destinataire ne paie une requete complete que s'il y a du nouveau.
    """

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Temps Reel',
            adresse='Conakry',
            telephone='+224600000010',
            directeur='Direction',
            etat='VALIDE',
        )
        self.poste = self._creer_poste('Poste secretariat')
        self.autre_poste = self._creer_poste('Poste direction')

    def _creer_poste(self, nom):
        token = secrets.token_urlsafe(32)
        device = SyncDevice(ecole=self.ecole, nom=nom)
        device.definir_token(token)
        device.save()
        return device, token

    def _pull(self, poste, **params):
        device, token = poste
        return self.client.get(
            reverse('synchronisation:pull'), params,
            HTTP_X_SYNC_DEVICE=str(device.device_id),
            HTTP_X_SYNC_TOKEN=token,
        )

    def test_une_saisie_faite_en_ligne_est_livree_aux_postes(self):
        """
        Le coeur du probleme : une saisie nee sur le serveur reste PENDING,
        faute d'un poste a qui la pousser. Tant que `pull` ne servait que les
        changements APPLIED, tout ce qui etait saisi sur le site en ligne
        n'atteignait aucun poste, quelle que soit la duree d'attente.
        """
        Classe.objects.create(
            ecole=self.ecole, nom='CP A', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        nee_en_ligne = SyncChange.objects.filter(model_label='eleves.Classe').get()
        self.assertEqual(nee_en_ligne.statut, SyncChange.STATUT_PENDING)
        self.assertIsNone(nee_en_ligne.device)

        recus = self._pull(self.poste).json()['changes']

        self.assertIn('eleves.Classe', {item['model_label'] for item in recus})

    def test_un_poste_ne_recoit_pas_son_propre_envoi(self):
        device, _ = self.poste
        SyncChange.objects.create(
            ecole=self.ecole, device=device, model_label='eleves.Classe',
            object_uuid=uuid.uuid4(), operation='CREATE',
            payload={}, statut=SyncChange.STATUT_APPLIED,
        )

        recus = self._pull(self.poste).json()['changes']

        self.assertEqual(
            [item for item in recus if item['device_name'] == 'Poste secretariat'], [],
        )

    def test_le_repere_avance_meme_quand_le_lot_est_vide(self):
        """
        Sans cela, un poste dont le dernier changement ne le concerne pas
        (le sien) garde un `since_id` fige : il redemande le meme intervalle a
        chaque cycle, et la cadence courte devient intenable.
        """
        device, _ = self.poste
        propre = SyncChange.objects.create(
            ecole=self.ecole, device=device, model_label='eleves.Classe',
            object_uuid=uuid.uuid4(), operation='CREATE',
            payload={}, statut=SyncChange.STATUT_APPLIED,
        )

        reponse = self._pull(self.poste, since_id=propre.id - 1).json()

        self.assertEqual(reponse['changes'], [])
        self.assertEqual(reponse['latest_change_id'], propre.id)

    def test_le_repere_ne_depasse_pas_un_envoi_en_cours_d_application(self):
        """
        Une ligne poussee par un autre poste et encore PENDING est sur le point
        de devenir livrable. Avancer le repere par-dessus la rendrait invisible
        a jamais.
        """
        autre, _ = self.autre_poste
        en_cours = SyncChange.objects.create(
            ecole=self.ecole, device=autre, model_label='eleves.Classe',
            object_uuid=uuid.uuid4(), operation='CREATE',
            payload={}, statut=SyncChange.STATUT_PENDING,
        )

        reponse = self._pull(self.poste, since_id=en_cours.id - 1).json()

        self.assertEqual(reponse['changes'], [])
        self.assertLess(reponse['latest_change_id'], en_cours.id)

    def test_le_poste_neuf_reprend_le_fil_apres_l_instantane(self):
        """
        L'instantane initial contient deja l'etat courant. Renvoyer le poste au
        debut de l'historique lui ferait rejouer des milliers de changements
        deja contenus dedans.
        """
        Classe.objects.create(
            ecole=self.ecole, nom='CP B', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        dernier = SyncChange.objects.order_by('-id').first()

        reponse = self._pull(self.poste, initial='1').json()

        self.assertTrue(reponse['initial'])
        self.assertEqual(reponse['latest_change_id'], dernier.id)

    def test_l_etat_sert_de_repere_de_fraicheur(self):
        device, token = self.poste
        Classe.objects.create(
            ecole=self.ecole, nom='CP C', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        dernier = SyncChange.objects.order_by('-id').first()

        reponse = self.client.get(
            reverse('synchronisation:state'),
            HTTP_X_SYNC_DEVICE=str(device.device_id),
            HTTP_X_SYNC_TOKEN=token,
        )

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['last_change_id'], dernier.id)
        self.assertIn('no-store', reponse['Cache-Control'])

    def test_l_etat_refuse_un_appelant_sans_identite(self):
        reponse = self.client.get(reverse('synchronisation:state'))
        self.assertEqual(reponse.status_code, 401)

    def test_l_etat_repond_a_une_page_ouverte_dans_le_navigateur(self):
        utilisateur = User.objects.create_user(username='caissiere', password='secret123')
        profil, _ = Profil.objects.get_or_create(user=utilisateur)
        profil.role = 'ADMIN'
        profil.ecole = self.ecole
        profil.save(update_fields=['role', 'ecole'])
        self.client.force_login(utilisateur)

        reponse = self.client.get(reverse('synchronisation:state'))

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['ecole_id'], self.ecole.pk)

    def test_une_ecriture_locale_reveille_la_synchronisation(self):
        """
        Sans ce reveil, la donnee attendait la fin du cycle en cours avant de
        partir. Le rappel est volontairement pose sur le commit : le worker vit
        dans un autre thread et lirait sinon une base ou rien n'est encore
        valide.
        """
        auto_sync._wake.clear()

        with self.captureOnCommitCallbacks(execute=True):
            Classe.objects.create(
                ecole=self.ecole, nom='CP D', niveau='PRIMAIRE_1',
                annee_scolaire='2026-2027',
            )
            self.assertFalse(auto_sync._wake.is_set())  # pas avant le commit

        self.assertTrue(auto_sync._wake.is_set())

    def test_une_suppression_locale_reveille_aussi_la_synchronisation(self):
        classe = Classe.objects.create(
            ecole=self.ecole, nom='CP E', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        auto_sync._wake.clear()

        with self.captureOnCommitCallbacks(execute=True):
            classe.delete()

        self.assertTrue(auto_sync._wake.is_set())


class CadenceSynchronisationTests(TestCase):
    """Le poste ne doit payer une requete complete que s'il y a du nouveau."""

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Cadence',
            adresse='Conakry',
            telephone='+224600000011',
            directeur='Direction',
            etat='VALIDE',
        )

    def test_rien_de_neuf_ne_declenche_aucun_telechargement(self):
        with mock.patch.object(auto_sync, '_load_since_id', return_value=57), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=57) as repere, \
                mock.patch.object(auto_sync, '_pull') as pull:
            self.assertEqual(
                auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole), 0,
            )

        repere.assert_called_once()
        pull.assert_not_called()

    def test_un_repere_qui_avance_declenche_le_telechargement(self):
        with mock.patch.object(auto_sync, '_load_since_id', return_value=57), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=58), \
                mock.patch.object(auto_sync, '_pull', return_value=3) as pull:
            self.assertEqual(
                auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole), 3,
            )

        pull.assert_called_once()

    def test_un_serveur_sans_la_route_retombe_sur_le_telechargement(self):
        """Compatibilite : un serveur non mis a jour ignore `/state/`."""
        with mock.patch.object(auto_sync, '_load_since_id', return_value=57), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=None), \
                mock.patch.object(auto_sync, '_pull', return_value=1) as pull:
            auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole)

        pull.assert_called_once()

    def test_la_cadence_suit_l_activite(self):
        auto_sync._mark_transfer()
        self.assertEqual(auto_sync._next_delay(True, 2, 10), 2)

        auto_sync._last_transfer = 0.0  # aucune activite recente
        self.assertEqual(auto_sync._next_delay(True, 2, 10), 10)

        # Hors-ligne : reessai rapproche pour rattraper des le retour du reseau.
        self.assertLessEqual(auto_sync._next_delay(False, 2, 3600), 15)

    def test_une_configuration_ancienne_reste_reactive(self):
        """
        Les postes deja installes portent un intervalle de 60 s. Sans plafond,
        ils resteraient a l'ancienne cadence sans que personne ne le voie.
        """
        with mock.patch.object(auto_sync.threading, 'Thread') as thread:
            auto_sync._started = False
            try:
                auto_sync.start(interval=3600, boot_delay=0, fast_interval=2)
            finally:
                auto_sync._started = False

        interval_retenu = thread.call_args.kwargs['args'][0]
        self.assertEqual(interval_retenu, auto_sync.MAX_IDLE_INTERVAL)

    def test_la_cadence_annoncee_est_celle_appliquee(self):
        """
        Le message de demarrage affichait la valeur du fichier de
        configuration, pas celle retenue : sur un poste regle a 60 s il
        annoncait une lenteur qui n'existait plus, de quoi envoyer chercher
        un probleme ailleurs.
        """
        repos, actif = auto_sync.cadence_effective(60, 2)

        self.assertEqual(repos, auto_sync.MAX_IDLE_INTERVAL)
        self.assertEqual(actif, 2)

    def test_une_cadence_deja_courte_est_laissee_telle_quelle(self):
        self.assertEqual(auto_sync.cadence_effective(10, 2), (10, 2))



class JetonAppareilTests(TestCase):
    """
    Le jeton est verifie a chaque appel : son cout devient structurel des que
    la cadence se resserre.
    """

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Jetons',
            adresse='Conakry',
            telephone='+224600000012',
            directeur='Direction',
            etat='VALIDE',
        )

    def test_un_jeton_valide_est_reconnu_et_un_autre_refuse(self):
        token = secrets.token_urlsafe(32)
        device = SyncDevice(ecole=self.ecole, nom='Poste')
        device.definir_token(token)
        device.save()

        self.assertTrue(device.verifier_token(token))
        self.assertFalse(device.verifier_token(token + 'x'))
        self.assertFalse(device.verifier_token(''))
        self.assertTrue(device.token_hash.startswith(SyncDevice.FAST_HASH_PREFIX))

    def test_un_poste_enregistre_avant_la_bascule_continue_de_fonctionner(self):
        from django.contrib.auth.hashers import make_password

        token = secrets.token_urlsafe(32)
        device = SyncDevice.objects.create(
            ecole=self.ecole, nom='Poste ancien', token_hash=make_password(token),
        )

        self.assertTrue(device.verifier_token(token))

        # Converti au passage : la lenteur ne se reproduit pas au prochain appel.
        device.refresh_from_db()
        self.assertTrue(device.token_hash.startswith(SyncDevice.FAST_HASH_PREFIX))
        self.assertTrue(device.verifier_token(token))


class ContratClientServeurTests(TestCase):
    """
    Le poste et le serveur sont les deux moities d'un meme echange, verifiees
    jusqu'ici chacune de son cote avec un faux interlocuteur.

    Ce test les branche l'un sur l'autre : le client parle a la vraie vue, par
    la vraie URL, avec les vrais en-tetes. Une faute de chemin ou un nom de
    champ divergent ne se verrait autrement qu'une fois deploye, sous la forme
    d'une synchronisation qui redevient lente sans que rien ne signale l'erreur.
    """

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Contrat',
            adresse='Conakry',
            telephone='+224600000013',
            directeur='Direction',
            etat='VALIDE',
        )
        self.token = secrets.token_urlsafe(32)
        self.device = SyncDevice(ecole=self.ecole, nom='Poste bout en bout')
        self.device.definir_token(self.token)
        self.device.save()

    def _transport(self, url, device_id, token, payload=None, method='POST', timeout=None):
        """Remplace urllib : la requete part vers la vraie vue Django."""
        chemin = url.replace('https://serveur', '')
        entetes = {'HTTP_X_SYNC_DEVICE': device_id, 'HTTP_X_SYNC_TOKEN': token}
        if method == 'GET':
            reponse = self.client.get(chemin, **entetes)
        else:
            reponse = self.client.post(
                chemin, data=json.dumps(payload or {}),
                content_type='application/json', **entetes,
            )
        self.assertEqual(reponse.status_code, 200, f'{chemin} -> {reponse.status_code}')
        return json.loads(reponse.content.decode('utf-8'))

    def test_le_repere_distant_est_lu_par_le_poste(self):
        Classe.objects.create(
            ecole=self.ecole, nom='CM1', niveau='PRIMAIRE_4',
            annee_scolaire='2026-2027',
        )
        dernier = SyncChange.objects.order_by('-id').first()

        with mock.patch.object(auto_sync, '_request_json', self._transport):
            repere = auto_sync._server_watermark(
                'https://serveur', str(self.device.device_id), self.token,
            )

        self.assertEqual(repere, dernier.id)

    def test_une_saisie_en_ligne_atteint_le_poste_en_un_cycle(self):
        classe_uuid = uuid.uuid4()
        Classe.objects.create(
            sync_uuid=classe_uuid, ecole=self.ecole, nom='CM2',
            niveau='PRIMAIRE_5', annee_scolaire='2026-2027',
        )

        change_attendu = SyncChange.objects.get(object_uuid=classe_uuid)

        with tempfile.TemporaryDirectory() as dossier:
            etat = os.path.join(dossier, '.sync_state.json')
            with mock.patch.object(auto_sync, '_state_path', return_value=etat), \
                    mock.patch.object(auto_sync, '_request_json', self._transport):
                recus = auto_sync._pull_if_needed(
                    'https://serveur', str(self.device.device_id), self.token, self.ecole,
                )

            with open(etat, encoding='utf-8') as fichier:
                repere_local = json.load(fichier)['since_id']

        # La saisie nee en ligne a bien traverse, et le poste a memorise
        # jusqu'ou il est alle : son prochain cycle repartira de la.
        self.assertGreaterEqual(recus, 1)
        self.assertGreaterEqual(repere_local, change_attendu.id)
        self.assertTrue(
            SyncChange.objects
            .filter(payload__server_change_id=change_attendu.id)
            .exists()
        )


class TraceDesEchecsTests(TestCase):
    """
    Le worker ne doit plus jamais echouer en silence.

    Un poste hors-ligne ou mal configure ne laissait litteralement aucune
    preuve dans les journaux avant ce correctif : trouve en verifiant, sur un
    poste reel, un appareil enregistre depuis la veille dont la colonne
    "Derniere connexion" affichait "Jamais", sans le moindre indice sur la
    cause.
    """

    def setUp(self):
        auto_sync._echecs_consecutifs = 0
        auto_sync._dernier_log_echec = 0.0

    def tearDown(self):
        auto_sync._echecs_consecutifs = 0
        auto_sync._dernier_log_echec = 0.0

    def test_le_premier_echec_est_trace_immediatement(self):
        with self.assertLogs('synchronisation.auto_sync', level='WARNING') as capture:
            auto_sync._signaler_echec('Serveur injoignable')
        self.assertIn('1 tentative', capture.output[0])
        self.assertIn('Serveur injoignable', capture.output[0])

    def test_les_echecs_suivants_rapproches_ne_reecrivent_pas_le_journal(self):
        """
        Un poste hors-ligne reessaie toutes les quelques secondes : sans cette
        limite, ce seul message noierait le reste du journal.
        """
        with mock.patch.object(auto_sync.time, 'monotonic', return_value=1000.0):
            auto_sync._signaler_echec('injoignable')  # 1er, trace immediatement

        # `assertNoLogs` n'existe qu'a partir de Django 4.1 ; on verifie
        # l'absence de nouveau log en constatant que le journal reste vide
        # apres l'appel, plutot que de compter sur `assertLogs` qui leverait
        # s'il ne voit rien.
        journal = mock.Mock()
        with mock.patch.object(auto_sync.logger, 'warning', journal), \
                mock.patch.object(auto_sync.time, 'monotonic', return_value=1005.0):
            auto_sync._signaler_echec('toujours injoignable')  # 5 s plus tard
        journal.assert_not_called()

    def test_un_echec_bien_plus_tard_est_retrace(self):
        auto_sync._signaler_echec('injoignable')
        auto_sync._dernier_log_echec -= auto_sync.INTERVALLE_LOG_ECHEC_SECONDES + 1

        with self.assertLogs('synchronisation.auto_sync', level='WARNING') as capture:
            auto_sync._signaler_echec('toujours injoignable')

        self.assertIn('2 tentative', capture.output[0])

    def test_le_retour_a_la_normale_est_trace_et_remet_le_compteur_a_zero(self):
        auto_sync._signaler_echec('injoignable')
        auto_sync._signaler_echec('injoignable')

        with self.assertLogs('synchronisation.auto_sync', level='INFO') as capture:
            auto_sync._signaler_succes()

        self.assertIn('2 tentative', capture.output[0])
        self.assertEqual(auto_sync._echecs_consecutifs, 0)

    def test_un_succes_sans_echec_prealable_ne_journalise_rien(self):
        auto_sync._signaler_succes()  # ne doit lever aucune exception
        self.assertEqual(auto_sync._echecs_consecutifs, 0)

    def test_un_cycle_en_erreur_reseau_declenche_la_trace(self):
        with override_settings(
            MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_ECOLE_ID='1',
            MYSCHOOL_SYNC_DEVICE_ID='11111111-1111-1111-1111-111111111111',
            MYSCHOOL_SYNC_TOKEN='jeton',
        ):
            with mock.patch.object(auto_sync, '_load_state', return_value={'initial_done': True}), \
                    mock.patch.object(auto_sync, '_local_school', return_value=mock.Mock(pk=1)), \
                    mock.patch.object(auto_sync, '_push', side_effect=URLError('injoignable')):
                with self.assertLogs('synchronisation.auto_sync', level='WARNING') as capture:
                    self.assertFalse(auto_sync._run_once())

        self.assertIn('injoignable', capture.output[0])

    def test_un_echec_sans_message_utilise_le_type_d_exception(self):
        """URLError() sans argument a un str() vide : le journal doit rester lisible."""
        with self.assertLogs('synchronisation.auto_sync', level='WARNING') as capture:
            auto_sync._signaler_echec(str(URLError('')) or 'URLError')
        self.assertTrue(capture.output)


class DiagnosticSynchronisationTests(TestCase):
    """
    `diagnostiquer_synchronisation()` doit donner, en un seul appel, ce que le
    worker en arriere-plan ne montrerait qu'apres plusieurs minutes de
    silence — et c'est precisement ce qui a manque pour diagnostiquer un poste
    reel dont le worker echouait sans laisser aucune trace.
    """

    @override_settings(MYSCHOOL_SYNC_SERVER_URL='', MYSCHOOL_SYNC_DEVICE_ID='',
                       MYSCHOOL_SYNC_TOKEN='', MYSCHOOL_SYNC_ECOLE_ID='')
    def test_sans_configuration_le_code_de_sortie_est_un_echec_explicite(self):
        with mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        self.assertTrue(any('incomplete' in str(appel) for appel in sortie.call_args_list))

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_un_succes_donne_le_code_zero_et_le_repere_local(self):
        with mock.patch.object(auto_sync, '_tenter_cycle', return_value=True), \
                mock.patch.object(auto_sync, '_load_state', return_value={'since_id': 42}), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 0)
        self.assertTrue(any('SUCCES' in str(appel) for appel in sortie.call_args_list))
        self.assertTrue(any('42' in str(appel) for appel in sortie.call_args_list))

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_une_exception_est_affichee_en_clair_pas_avalee(self):
        """
        Le defaut trouve sur un poste reel : le worker en arriere-plan
        n'affichait jamais la cause d'un echec. Ce chemin-ci ne doit RIEN
        avaler.
        """
        with mock.patch.object(auto_sync, '_tenter_cycle',
                               side_effect=URLError('injoignable pour de vrai')), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        texte = ' '.join(str(appel) for appel in sortie.call_args_list)
        self.assertIn('injoignable pour de vrai', texte)
        self.assertIn('URLError', texte)

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_une_erreur_de_certificat_est_reconnue_et_expliquee(self):
        """
        L'hypothese principale pour un poste d'ecole derriere un pare-feu qui
        inspecte le HTTPS : Windows (et un navigateur) fait confiance au
        certificat, le Python embarque non. Ce cas doit etre nomme
        explicitement, pas noye dans un message technique generique.
        """
        import ssl
        erreur = ssl.SSLCertVerificationError(
            'certificate verify failed: unable to get local issuer certificate',
        )
        with mock.patch.object(auto_sync, '_tenter_cycle', side_effect=erreur), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        texte = ' '.join(str(appel) for appel in sortie.call_args_list)
        self.assertIn('certificat', texte.lower())
        self.assertIn('pare-feu', texte.lower())

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_un_403_suggere_de_revoquer_et_regenerer_le_poste(self):
        erreur = HTTPError('https://serveur', 403, 'Forbidden', {}, None)
        with mock.patch.object(auto_sync, '_tenter_cycle', side_effect=erreur), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        texte = ' '.join(str(appel) for appel in sortie.call_args_list)
        self.assertIn('Revoquez', texte)

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_une_base_non_migree_est_expliquee_pas_affichee_en_brut(self):
        """
        Trouve en testant l'executable compile sur un dossier fraichement
        deploye, jamais lance normalement : la table n'existe pas encore, et
        sans ce cas le diagnostic affichait une erreur SQL brute plutot
        qu'une instruction actionnable.
        """
        erreur = Exception('no such table: eleves_ecole')
        with mock.patch.object(auto_sync, '_tenter_cycle', side_effect=erreur), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        texte = ' '.join(str(appel) for appel in sortie.call_args_list)
        self.assertIn('initialisee', texte)

    @override_settings(
        MYSCHOOL_SYNC_SERVER_URL='https://serveur', MYSCHOOL_SYNC_DEVICE_ID='d',
        MYSCHOOL_SYNC_TOKEN='t', MYSCHOOL_SYNC_ECOLE_ID='1',
    )
    def test_un_echec_sans_exception_reste_explicite(self):
        """Ecole locale introuvable ou serveur qui ne la reconnait pas : pas de crash, un message."""
        with mock.patch.object(auto_sync, '_tenter_cycle', return_value=False), \
                mock.patch('builtins.print') as sortie:
            code = auto_sync.diagnostiquer_synchronisation()
        self.assertEqual(code, 1)
        texte = ' '.join(str(appel) for appel in sortie.call_args_list)
        self.assertIn('Echec', texte)

    def test_le_cycle_normal_delegue_toujours_a_tenter_cycle(self):
        """Le refactor ne doit rien changer au comportement externe de _run_once."""
        with mock.patch.object(auto_sync, '_tenter_cycle', return_value=True):
            self.assertTrue(auto_sync._run_once())
        with mock.patch.object(auto_sync, '_tenter_cycle', return_value=False):
            self.assertFalse(auto_sync._run_once())
