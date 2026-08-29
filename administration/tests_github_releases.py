"""
Les publications GitHub comme source des versions de l'application.

Deux exigences dominent ces tests. La premiere : rien ne s'installe sans
empreinte verifiable — le poste telecharge un executable et le lance. La
seconde : la decision reste au serveur. Decocher « publiee » doit arreter la
diffusion partout, et ni l'import automatique ni le recours a GitHub ne
doivent pouvoir contourner ce geste.
"""
import json
import secrets
from unittest import mock
from urllib.error import HTTPError, URLError

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from ecole_moderne import auto_mise_a_jour
from eleves.models import Ecole
from synchronisation.models import SyncDevice

from . import github_releases
from .models import VersionApplication


def _release(version='1.4.0', *, digest=True, exe=True, **extra):
    nom = f'MySchoolGN_Setup_v{version}.exe'
    actifs = []
    if exe:
        actifs.append({
            'name': nom,
            'size': 74577428,
            'digest': f'sha256:{"a" * 64}' if digest else None,
            'browser_download_url': (
                f'https://github.com/org/depot/releases/download/desktop-v{version}/{nom}'
            ),
        })
    release = {
        'tag_name': f'desktop-v{version}',
        'body': f'Nouveautes de la version {version}',
        'draft': False,
        'prerelease': False,
        'assets': actifs,
    }
    release.update(extra)
    return release


class LectureDesPublicationsTests(TestCase):
    """Traduction d'une publication GitHub en descripteur de version."""

    def _lire(self, releases, contenu_voisin=None):
        def _faux(url, json_attendu=True, **kwargs):
            if json_attendu:
                return releases
            return contenu_voisin
        return mock.patch.object(github_releases, '_lire', side_effect=_faux)

    @override_settings(MYSCHOOL_GITHUB_REPO='')
    def test_le_depot_par_defaut_est_celui_des_jardins_wosewa(self):
        self.assertEqual(
            github_releases._depot(), 'Faraleno2022/lesjardinswosewa',
        )

    def test_une_publication_devient_un_descripteur_complet(self):
        with self._lire([_release('1.4.0')]):
            descripteurs = github_releases.versions_disponibles()

        self.assertEqual(len(descripteurs), 1)
        descripteur = descripteurs[0]
        self.assertEqual(descripteur['version'], '1.4.0')
        self.assertEqual(descripteur['tag'], 'desktop-v1.4.0')
        self.assertEqual(descripteur['sha256'], 'a' * 64)
        self.assertEqual(descripteur['taille_octets'], 74577428)
        self.assertTrue(descripteur['url'].startswith('https://'))

    def test_le_numero_est_extrait_du_tag_quel_que_soit_son_prefixe(self):
        with self._lire([_release('2.0.1')]):
            self.assertEqual(
                github_releases.versions_disponibles()[0]['version'], '2.0.1',
            )

    def test_un_brouillon_et_une_preversion_sont_ecartes(self):
        """Ces deux etats disent exactement « pas encore pour les postes »."""
        releases = [
            _release('1.5.0', draft=True),
            _release('1.6.0', prerelease=True),
            _release('1.4.0'),
        ]
        with self._lire(releases):
            descripteurs = github_releases.versions_disponibles()

        self.assertEqual([d['version'] for d in descripteurs], ['1.4.0'])

    def test_une_publication_sans_empreinte_est_ignoree(self):
        """
        Le poste lance ce fichier. Sans empreinte, rien ne distingue
        l'installateur attendu d'un autre : mieux vaut ne rien proposer.
        """
        with self._lire([_release('1.4.0', digest=False)], contenu_voisin=b''):
            self.assertEqual(github_releases.versions_disponibles(), [])

    def test_l_empreinte_est_lue_dans_le_fichier_voisin_a_defaut_du_champ(self):
        """Compatibilite avec les publications anterieures au champ `digest`."""
        release = _release('1.4.0', digest=False)
        release['assets'].append({
            'name': 'MySchoolGN_Setup_v1.4.0.exe.sha256',
            'browser_download_url': 'https://github.com/org/depot/x.sha256',
        })
        empreinte = 'b' * 64
        voisin = f'{empreinte} *MySchoolGN_Setup_v1.4.0.exe\n'.encode()

        with self._lire([release], contenu_voisin=voisin):
            descripteurs = github_releases.versions_disponibles()

        self.assertEqual(descripteurs[0]['sha256'], empreinte)

    def test_une_publication_sans_installateur_est_ignoree(self):
        with self._lire([_release('1.4.0', exe=False)]):
            self.assertEqual(github_releases.versions_disponibles(), [])

    def test_une_adresse_non_chiffree_est_refusee(self):
        release = _release('1.4.0')
        release['assets'][0]['browser_download_url'] = 'http://github.com/x.exe'
        with self._lire([release]):
            self.assertEqual(github_releases.versions_disponibles(), [])

    def test_la_derniere_version_est_la_plus_haute_pas_la_plus_recente(self):
        """
        Republier un correctif sur une branche ancienne ne doit pas faire
        redescendre les postes d'une version.
        """
        with self._lire([_release('1.2.9'), _release('1.10.0')]):
            derniere = github_releases.derniere_version_github()

        self.assertEqual(derniere['version'], '1.10.0')


class ImportDesPublicationsTests(TestCase):
    """Recopie des publications dans la table que consultent les postes."""

    def setUp(self):
        cache.clear()

    def _importer(self, releases):
        with mock.patch.object(
            github_releases, 'versions_disponibles', return_value=releases,
        ):
            return github_releases.importer_versions()

    def _descripteur(self, version='1.4.0', **extra):
        descripteur = {
            'version': version,
            'tag': f'desktop-v{version}',
            'url': f'https://github.com/org/d/MySchoolGN_Setup_v{version}.exe',
            'sha256': 'a' * 64,
            'taille_octets': 100,
            'notes': 'Corrections',
        }
        descripteur.update(extra)
        return descripteur

    def test_une_publication_devient_une_version_mise_a_disposition(self):
        """
        Publier une release EST l'acte de mise a disposition. Exiger une
        seconde validation ici recreerait l'oubli que ce mecanisme supprime :
        des versions publiees mais invisibles des postes.
        """
        creees, modifiees = self._importer([self._descripteur()])

        self.assertEqual((creees, modifiees), (1, 0))
        version = VersionApplication.objects.get(version='1.4.0')
        self.assertTrue(version.publiee)
        self.assertIsNotNone(version.date_publication)
        self.assertEqual(version.sha256, 'a' * 64)

    def test_un_second_import_ne_cree_pas_de_doublon(self):
        self._importer([self._descripteur()])
        creees, modifiees = self._importer([self._descripteur()])

        self.assertEqual((creees, modifiees), (0, 0))
        self.assertEqual(VersionApplication.objects.count(), 1)

    def test_une_empreinte_corrigee_est_rafraichie(self):
        self._importer([self._descripteur()])
        creees, modifiees = self._importer([self._descripteur(sha256='c' * 64)])

        self.assertEqual((creees, modifiees), (0, 1))
        self.assertEqual(
            VersionApplication.objects.get(version='1.4.0').sha256, 'c' * 64,
        )

    def test_une_version_depubliee_a_la_main_le_reste(self):
        """
        Decocher la case est la seule facon d'arreter une version defectueuse.
        Un import qui la recocherait la relancerait sur tous les postes.
        """
        self._importer([self._descripteur()])
        VersionApplication.objects.filter(version='1.4.0').update(publiee=False)

        self._importer([self._descripteur(notes='Autres corrections')])

        version = VersionApplication.objects.get(version='1.4.0')
        self.assertFalse(version.publiee)
        self.assertEqual(version.notes, 'Autres corrections')

    def test_une_publication_invalide_n_interrompt_pas_les_autres(self):
        creees, _ = self._importer([
            self._descripteur('1.4.0', sha256='trop-court'),
            self._descripteur('1.5.0'),
        ])

        self.assertEqual(creees, 1)
        self.assertFalse(VersionApplication.objects.filter(version='1.4.0').exists())
        self.assertTrue(VersionApplication.objects.filter(version='1.5.0').exists())

    def test_une_panne_de_github_ne_leve_pas(self):
        """Le serveur doit continuer a repondre avec ce qu'il connait deja."""
        with mock.patch.object(
            github_releases, 'versions_disponibles', side_effect=URLError('coupe'),
        ):
            self.assertEqual(github_releases.importer_versions(), (0, 0))

    def test_l_import_automatique_est_verrouille_dans_le_temps(self):
        """
        Le quota anonyme de GitHub est de 60 appels par heure et par adresse
        IP, partagee sur un hebergement mutualise : une centaine de postes ne
        doit pas provoquer une centaine d'appels.
        """
        with mock.patch.object(github_releases, 'importer_versions') as importer:
            self.assertTrue(github_releases.importer_si_necessaire())
            self.assertFalse(github_releases.importer_si_necessaire())
            self.assertFalse(github_releases.importer_si_necessaire())

        importer.assert_called_once()

    @override_settings(MYSCHOOL_GITHUB_AUTO_IMPORT=False)
    def test_l_import_automatique_peut_etre_coupe(self):
        with mock.patch.object(github_releases, 'importer_versions') as importer:
            self.assertFalse(github_releases.importer_si_necessaire())
            self.assertFalse(github_releases.declencher_import_en_arriere_plan())

        importer.assert_not_called()

    def test_l_import_en_arriere_plan_obeit_au_meme_verrou(self):
        with mock.patch.object(github_releases.threading, 'Thread') as thread:
            self.assertTrue(github_releases.declencher_import_en_arriere_plan())
            self.assertFalse(github_releases.declencher_import_en_arriere_plan())

        thread.assert_called_once()
        thread.return_value.start.assert_called_once()

    def test_le_fil_d_arriere_plan_rend_sa_connexion(self):
        """
        Un fil qui garde sa connexion ouverte en accumule une par import, et
        c'est le nombre de connexions simultanees qui est compte sur un
        hebergement mutualise.
        """
        with mock.patch.object(github_releases, 'importer_versions'), \
                mock.patch('django.db.connection.close') as fermer:
            github_releases._importer_puis_liberer()

        fermer.assert_called_once()

    def test_une_panne_dans_le_fil_n_empeche_pas_la_fermeture(self):
        with mock.patch.object(
            github_releases, 'importer_versions', side_effect=URLError('coupe'),
        ), mock.patch('django.db.connection.close') as fermer:
            github_releases._importer_puis_liberer()  # ne doit pas lever

        fermer.assert_called_once()


class ImportDeclencheParLesPostesTests(TestCase):
    """
    Une release publiee doit atteindre les postes sans qu'un humain lance quoi
    que ce soit : c'est la question posee par le poste qui declenche l'import.
    """

    def setUp(self):
        cache.clear()
        self.ecole = Ecole.objects.create(
            nom='Ecole MAJ GitHub',
            adresse='Conakry',
            telephone='+224600000031',
            directeur='Direction',
            etat='VALIDE',
        )
        self.token = secrets.token_urlsafe(32)
        self.device = SyncDevice(ecole=self.ecole, nom='Poste')
        self.device.definir_token(self.token)
        self.device.save()
        self.url = reverse('mises_a_jour:derniere_version')

    def _demander(self, version='1.0.0'):
        return self.client.get(self.url, {'version': version}, **{
            'HTTP_X_SYNC_DEVICE': str(self.device.device_id),
            'HTTP_X_SYNC_TOKEN': self.token,
        })

    def _publier(self, version='1.4.0'):
        return VersionApplication.objects.create(
            version=version,
            url_telechargement='https://github.com/org/d/setup.exe',
            sha256='a' * 64,
            publiee=True,
        )

    def test_la_question_d_un_poste_declenche_l_import(self):
        with mock.patch.object(
            github_releases, 'declencher_import_en_arriere_plan',
        ) as declencher:
            self._demander()

        declencher.assert_called_once()

    def test_la_requete_du_poste_n_attend_pas_github(self):
        """
        Sur un hebergement mutualise, chaque requete en cours immobilise l'un
        des rares processus qui servent aussi le site public : un aller-retour
        vers GitHub n'a rien a y faire.
        """
        appels = []

        def _thread(target=None, **kwargs):
            appels.append(kwargs.get('daemon'))
            faux = mock.MagicMock()
            faux.start = mock.MagicMock()
            return faux

        with mock.patch.object(github_releases.threading, 'Thread', side_effect=_thread), \
                mock.patch.object(github_releases, 'importer_versions') as importer:
            reponse = self._demander()

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(appels, [True])  # un fil detache, pas la requete
        importer.assert_not_called()  # rien n'a tourne dans la requete

    def test_la_version_importee_est_servie_a_la_question_suivante(self):
        with mock.patch.object(github_releases, 'declencher_import_en_arriere_plan'):
            self.assertFalse(self._demander().json()['mise_a_jour_disponible'])

            self._publier('1.4.0')  # ce que l'import d'arriere-plan aurait ecrit
            donnees = self._demander().json()

        self.assertTrue(donnees['mise_a_jour_disponible'])
        self.assertEqual(donnees['version'], '1.4.0')

    def test_une_panne_de_github_ne_casse_pas_la_reponse(self):
        self._publier('1.4.0')

        with mock.patch.object(
            github_releases, 'declencher_import_en_arriere_plan',
            side_effect=URLError('coupe'),
        ):
            reponse = self._demander()

        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()['version'], '1.4.0')


class RecoursGitHubDuPosteTests(TestCase):
    """
    Le poste interroge son serveur en premier. GitHub n'est un recours que
    lorsque ce serveur n'a pas repondu du tout.
    """

    def _reponse_serveur(self, **extra):
        reponse = {'ok': True, 'mise_a_jour_disponible': False}
        reponse.update(extra)
        return reponse

    def _github(self, version='9.9.9'):
        return {
            'version': version,
            'url': f'https://github.com/org/d/MySchoolGN_Setup_v{version}.exe',
            'sha256': 'a' * 64,
            'taille_octets': 100,
            'notes': 'Depuis GitHub',
        }

    def test_le_serveur_est_interroge_en_premier(self):
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=('https://s', 'd', 't')), \
                mock.patch.object(
                    auto_mise_a_jour, '_demander_derniere_version',
                    return_value=self._reponse_serveur(
                        mise_a_jour_disponible=True, version='9.9.9',
                        url='https://s/x.exe', sha256='a' * 64,
                    ),
                ), \
                mock.patch.object(auto_mise_a_jour, '_demander_github') as github:
            descripteur = auto_mise_a_jour._descripteur_distant()

        self.assertEqual(descripteur['version'], '9.9.9')
        github.assert_not_called()

    def test_un_rien_de_neuf_du_serveur_est_definitif(self):
        """
        Sinon, depublier une version defectueuse cote serveur n'aurait plus
        aucun effet : le poste irait la rechercher sur GitHub.
        """
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=('https://s', 'd', 't')), \
                mock.patch.object(
                    auto_mise_a_jour, '_demander_derniere_version',
                    return_value=self._reponse_serveur(),
                ), \
                mock.patch.object(auto_mise_a_jour, '_demander_github') as github:
            self.assertIsNone(auto_mise_a_jour._descripteur_distant())

        github.assert_not_called()

    def test_un_serveur_injoignable_bascule_sur_github(self):
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=('https://s', 'd', 't')), \
                mock.patch.object(
                    auto_mise_a_jour, '_demander_derniere_version',
                    side_effect=URLError('reseau coupe'),
                ), \
                mock.patch.object(
                    github_releases, 'derniere_version_github', return_value=self._github(),
                ):
            descripteur = auto_mise_a_jour._descripteur_distant()

        self.assertTrue(descripteur['mise_a_jour_disponible'])
        self.assertEqual(descripteur['version'], '9.9.9')
        self.assertEqual(descripteur['sha256'], 'a' * 64)

    def test_un_poste_revoque_ne_contourne_pas_le_refus_par_github(self):
        """
        Un HTTP 403 n'est pas une panne : le serveur a repondu, et sa reponse
        est que ce poste n'est plus autorise.
        """
        refus = HTTPError('https://s', 403, 'Interdit', {}, None)
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=('https://s', 'd', 't')), \
                mock.patch.object(
                    auto_mise_a_jour, '_demander_derniere_version', side_effect=refus,
                ), \
                mock.patch.object(auto_mise_a_jour, '_demander_github') as github:
            self.assertIsNone(auto_mise_a_jour._descripteur_distant())

        github.assert_not_called()

    def test_un_poste_autonome_se_met_a_jour_par_github(self):
        """Une installation jamais reliee a un serveur reste maintenue."""
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=None), \
                mock.patch.object(
                    github_releases, 'derniere_version_github', return_value=self._github(),
                ):
            descripteur = auto_mise_a_jour._descripteur_distant()

        self.assertEqual(descripteur['version'], '9.9.9')

    def test_une_version_github_plus_ancienne_est_ignoree(self):
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=None), \
                mock.patch.object(
                    github_releases, 'derniere_version_github',
                    return_value=self._github('0.0.1'),
                ):
            self.assertIsNone(auto_mise_a_jour._descripteur_distant())

    def test_une_version_github_n_est_jamais_imposee(self):
        """
        Imposer une installation est une decision du serveur. Un poste coupe
        de son serveur est justement celui a qui on ne veut rien imposer.
        """
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=None), \
                mock.patch.object(
                    github_releases, 'derniere_version_github', return_value=self._github(),
                ):
            self.assertFalse(auto_mise_a_jour._descripteur_distant()['obligatoire'])

    def test_github_injoignable_ne_leve_pas(self):
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=None), \
                mock.patch.object(
                    github_releases, 'derniere_version_github',
                    side_effect=URLError('coupe'),
                ):
            self.assertIsNone(auto_mise_a_jour._descripteur_distant())
