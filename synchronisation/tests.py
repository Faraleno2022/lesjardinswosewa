import json
import os
import shutil
import tempfile
import uuid
from unittest import mock

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
        self.assertEqual(len(response.json()['changes']), 1)


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
