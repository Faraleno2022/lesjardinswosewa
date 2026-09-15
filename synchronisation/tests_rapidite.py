"""
Ce qui rend la propagation rapide entre le serveur et un poste hors ligne.

Trois mecanismes sont couverts ici, tous invisibles depuis l'interface mais
directement responsables du delai entre une saisie et son apparition ailleurs :
l'enchainement des lots dans un meme cycle (envoi et reception), l'arret propre
de ces boucles, et la compression des echanges.
"""
import gzip
import json
import uuid
from unittest import mock

from django.test import TestCase

from eleves.models import Ecole

from . import auto_sync
from .models import SyncChange


class RattrapageEnUnCycleTests(TestCase):
    """
    Le serveur ne sert que 200 changements par requete, et le poste n'en
    traitait qu'un lot par cycle : un poste rentre apres plusieurs jours hors
    ligne descendait 200 changements toutes les quelques secondes, en affichant
    entre-temps des donnees incompletes. Les lots s'enchainent desormais dans
    le meme cycle.
    """

    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Rattrapage',
            adresse='Conakry',
            telephone='+224600000021',
            directeur='Direction',
            etat='VALIDE',
        )
        SyncChange.objects.filter(ecole=self.ecole).delete()

    # ─── Reception ───────────────────────────────────────────────────────────
    def test_la_reception_enchaine_les_lots_jusqu_au_filigrane(self):
        repere = {'valeur': 0}
        lots = []

        def _faux_pull(*args, **kwargs):
            lots.append(1)
            repere['valeur'] += 200
            return 200, 200

        with mock.patch.object(auto_sync, '_since_local', side_effect=lambda: repere['valeur']), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=600), \
                mock.patch.object(auto_sync, '_pull', side_effect=_faux_pull):
            applique = auto_sync._pull_if_needed(
                'https://serveur', 'device', 'token', self.ecole,
            )

        self.assertEqual(len(lots), 3)  # 600 changements en un seul cycle
        self.assertEqual(applique, 600)

    def test_un_lot_vide_arrete_la_boucle(self):
        """Sans cette sortie, un serveur muet ferait tourner le cycle a vide."""
        with mock.patch.object(auto_sync, '_since_local', return_value=0), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=9999), \
                mock.patch.object(auto_sync, '_pull', return_value=(0, 0)) as pull:
            auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole)

        pull.assert_called_once()

    def test_un_repere_qui_stagne_arrete_la_boucle(self):
        """
        Un lot recu sans que le repere avance signale une anomalie serveur.
        Continuer redemanderait le meme intervalle a l'infini.
        """
        with mock.patch.object(auto_sync, '_since_local', return_value=57), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=9999), \
                mock.patch.object(auto_sync, '_pull', return_value=(5, 5)) as pull:
            auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole)

        pull.assert_called_once()

    def test_le_nombre_de_lots_par_cycle_reste_borne(self):
        """
        Un rattrapage gigantesque ne doit pas monopoliser indefiniment le fil
        d'arriere-plan : le reste descendra au cycle suivant, deux secondes
        plus tard.
        """
        repere = {'valeur': 0}

        def _faux_pull(*args, **kwargs):
            repere['valeur'] += 200
            return 200, 200

        with mock.patch.object(auto_sync, '_since_local', side_effect=lambda: repere['valeur']), \
                mock.patch.object(auto_sync, '_server_watermark', return_value=10 ** 9), \
                mock.patch.object(auto_sync, '_pull', side_effect=_faux_pull) as pull:
            auto_sync._pull_if_needed('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(pull.call_count, auto_sync.MAX_LOTS_PAR_CYCLE)

    # ─── Envoi ───────────────────────────────────────────────────────────────
    def _changements_locaux(self, nombre):
        for index in range(nombre):
            SyncChange.objects.create(
                ecole=self.ecole,
                model_label='eleves.Classe',
                object_uuid=uuid.uuid4(),
                operation=SyncChange.OPERATION_CREATE,
                payload={'nom': f'CP {index}'},
            )

    def test_l_envoi_vide_toute_la_file_en_un_cycle(self):
        self._changements_locaux(450)
        lots = []

        def _faux_request(url, device_id, token, payload=None, **kwargs):
            lots.append(len(payload['changes']))
            return {
                'ok': True,
                'accepted': [{'index': i} for i in range(len(payload['changes']))],
            }

        with mock.patch.object(auto_sync, '_request_json', _faux_request):
            total = auto_sync._push_tout('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(lots, [200, 200, 50])
        self.assertEqual(total, 450)
        self.assertFalse(
            SyncChange.objects.filter(
                ecole=self.ecole, statut=SyncChange.STATUT_PENDING,
            ).exists()
        )

    def test_un_refus_n_est_pas_represente_dans_le_meme_cycle(self):
        """
        Le budget de tentatives est prevu pour s'etaler sur plusieurs cycles,
        le temps qu'une dependance manquante arrive. Une boucle naive le
        consommerait en entier en quelques millisecondes, et le changement
        serait abandonne alors qu'il aurait fini par passer.
        """
        self._changements_locaux(1)
        envois = []

        def _faux_request(url, device_id, token, payload=None, **kwargs):
            envois.append(payload['changes'])
            return {
                'ok': True,
                'accepted': [],
                'rejected': [{'index': 0, 'error': 'Relation introuvable pour ecole.'}],
            }

        with mock.patch.object(auto_sync, '_request_json', _faux_request):
            auto_sync._push_tout('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(len(envois), 1)  # une seule presentation, pas 25
        change = SyncChange.objects.get(ecole=self.ecole)
        self.assertEqual(change.tentatives, 1)
        self.assertEqual(change.statut, SyncChange.STATUT_PENDING)

    def test_un_refus_ne_bloque_pas_les_changements_suivants(self):
        """
        Le curseur avance lot par lot : un changement refuse ne doit pas
        retenir derriere lui tout ce qui a ete saisi apres lui.
        """
        self._changements_locaux(250)

        def _faux_request(url, device_id, token, payload=None, **kwargs):
            # Le tout premier changement du tout premier lot est refuse.
            refuses = [0] if payload['changes'][0]['payload']['nom'] == 'CP 0' else []
            return {
                'ok': True,
                'accepted': [
                    {'index': i} for i in range(len(payload['changes']))
                    if i not in refuses
                ],
                'rejected': [
                    {'index': i, 'error': 'Relation introuvable.'} for i in refuses
                ],
            }

        with mock.patch.object(auto_sync, '_request_json', _faux_request):
            total = auto_sync._push_tout('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(total, 249)
        restants = SyncChange.objects.filter(
            ecole=self.ecole, statut=SyncChange.STATUT_PENDING,
        )
        self.assertEqual(restants.count(), 1)
        self.assertEqual(restants.first().payload['nom'], 'CP 0')

    def test_un_serveur_qui_refuse_le_lot_entier_arrete_la_boucle(self):
        self._changements_locaux(10)
        envois = []

        def _faux_request(url, device_id, token, payload=None, **kwargs):
            envois.append(payload['changes'])
            return {'ok': False, 'error': 'Indisponible'}

        with mock.patch.object(auto_sync, '_request_json', _faux_request):
            total = auto_sync._push_tout('https://serveur', 'device', 'token', self.ecole)

        self.assertEqual(len(envois), 1)
        self.assertEqual(total, 0)


class CompressionDesEchangesTests(TestCase):
    """
    Un lot de reception transporte les photos d'eleves encodees en base64 :
    la reponse se compte en megaoctets. Le serveur sait compresser, mais
    seulement si le client l'annonce — ce que `urllib` ne fait pas seul.
    """

    def _reponse_simulee(self, corps, encodage=None):
        faux = mock.MagicMock()
        faux.read.return_value = corps
        faux.headers = {'Content-Encoding': encodage} if encodage else {}
        faux.__enter__.return_value = faux
        faux.__exit__.return_value = False
        return faux

    def test_la_compression_est_demandee(self):
        corps = json.dumps({'ok': True, 'changes': []}).encode('utf-8')

        with mock.patch.object(auto_sync.urlrequest, 'urlopen') as urlopen:
            urlopen.return_value = self._reponse_simulee(corps)
            auto_sync._request_json(
                'https://serveur/api/v1/sync/pull/', 'device', 'token',
                payload=None, method='GET',
            )

        requete = urlopen.call_args.args[0]
        self.assertEqual(requete.get_header('Accept-encoding'), 'gzip')

    def test_une_reponse_compressee_est_decompressee(self):
        attendu = {'ok': True, 'changes': [{'id': 1}]}
        corps = gzip.compress(json.dumps(attendu).encode('utf-8'))

        with mock.patch.object(auto_sync.urlrequest, 'urlopen') as urlopen:
            urlopen.return_value = self._reponse_simulee(corps, encodage='gzip')
            recu = auto_sync._request_json(
                'https://serveur/api/v1/sync/pull/', 'device', 'token',
                payload=None, method='GET',
            )

        self.assertEqual(recu, attendu)

    def test_une_reponse_non_compressee_reste_lisible(self):
        """Un serveur ancien, ou un intermediaire qui retire l'encodage."""
        attendu = {'ok': True, 'last_change_id': 42}
        corps = json.dumps(attendu).encode('utf-8')

        with mock.patch.object(auto_sync.urlrequest, 'urlopen') as urlopen:
            urlopen.return_value = self._reponse_simulee(corps)
            recu = auto_sync._request_json(
                'https://serveur/api/v1/sync/state/', 'device', 'token',
                payload=None, method='GET',
            )

        self.assertEqual(recu, attendu)
