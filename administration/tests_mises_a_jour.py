"""
Diffusion et installation des mises a jour de l'application Windows.

L'enjeu de ces tests n'est pas seulement qu'une version parvienne aux postes :
c'est qu'aucun fichier non verifie ne soit jamais execute. Un poste telecharge
ici un installateur et le lance avec les droits de l'utilisateur.
"""
import hashlib
import json
import os
import secrets
import tempfile
from unittest import mock

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from ecole_moderne import auto_mise_a_jour
from ecole_moderne.version import APP_VERSION, est_plus_recente, numero_de_version
from eleves.models import Ecole
from synchronisation.models import SyncDevice

from .models import VersionApplication


class NumeroDeVersionTests(TestCase):
    def test_la_comparaison_est_numerique_et_non_alphabetique(self):
        """"1.10.0" vient apres "1.9.0" : une comparaison de chaines dirait l'inverse."""
        self.assertTrue(est_plus_recente('1.10.0', '1.9.0'))
        self.assertFalse(est_plus_recente('1.9.0', '1.10.0'))

    def test_une_version_identique_n_est_pas_plus_recente(self):
        self.assertFalse(est_plus_recente('1.2.1', '1.2.1'))
        self.assertFalse(est_plus_recente(APP_VERSION))

    def test_les_formats_incomplets_ou_bruites_sont_tolerés(self):
        self.assertEqual(numero_de_version('1.3'), (1, 3, 0))
        self.assertEqual(numero_de_version('v1.3.2'), (1, 3, 2))
        self.assertEqual(numero_de_version(''), (0, 0, 0))
        self.assertFalse(est_plus_recente(None))


class VersionApplicationTests(TestCase):
    def _version(self, **extra):
        donnees = {
            'version': '9.0.0',
            'url_telechargement': 'https://exemple.test/MySchoolGN_Setup.exe',
            'sha256': 'a' * 64,
        }
        donnees.update(extra)
        return VersionApplication(**donnees)

    def test_une_empreinte_malformee_est_refusee(self):
        """Sans empreinte exploitable, rien ne distingue le bon fichier d'un autre."""
        with self.assertRaises(ValidationError) as erreur:
            self._version(sha256='trop-court').full_clean()
        self.assertIn('sha256', erreur.exception.message_dict)

    def test_une_adresse_non_chiffree_est_refusee(self):
        with self.assertRaises(ValidationError) as erreur:
            self._version(url_telechargement='http://exemple.test/setup.exe').full_clean()
        self.assertIn('url_telechargement', erreur.exception.message_dict)

    def test_la_date_de_publication_est_posee_a_la_publication(self):
        version = self._version(publiee=True)
        version.save()
        self.assertIsNotNone(version.date_publication)

    def test_la_derniere_publiee_est_la_plus_haute_pas_la_plus_recente(self):
        """
        Republier un correctif ancien ne doit pas faire redescendre les postes
        d'une version.
        """
        self._version(version='2.0.0', publiee=True).save()
        self._version(version='1.9.9', publiee=True).save()

        self.assertEqual(VersionApplication.derniere_publiee().version, '2.0.0')

    def test_un_brouillon_reste_invisible(self):
        self._version(version='3.0.0', publiee=False).save()
        self.assertIsNone(VersionApplication.derniere_publiee())


class EndpointMisesAJourTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole MAJ', adresse='Conakry', telephone='+224600000020',
            directeur='Direction', etat='VALIDE',
        )
        self.token = secrets.token_urlsafe(32)
        self.device = SyncDevice(ecole=self.ecole, nom='Poste a mettre a jour')
        self.device.definir_token(self.token)
        self.device.save()
        self.url = reverse('mises_a_jour:derniere_version')

    def _demander(self, version, **entetes):
        defaut = {
            'HTTP_X_SYNC_DEVICE': str(self.device.device_id),
            'HTTP_X_SYNC_TOKEN': self.token,
        }
        defaut.update(entetes)
        return self.client.get(self.url, {'version': version}, **defaut)

    def _publier(self, version='9.9.9'):
        VersionApplication.objects.create(
            version=version,
            url_telechargement='https://exemple.test/setup.exe',
            sha256='b' * 64, taille_octets=1234, notes='Corrections',
            publiee=True,
        )

    def test_un_poste_a_jour_ne_recoit_rien(self):
        self._publier('1.0.0')
        donnees = self._demander('1.0.0').json()
        self.assertFalse(donnees['mise_a_jour_disponible'])

    def test_un_poste_en_retard_recoit_le_descripteur_complet(self):
        self._publier('9.9.9')

        donnees = self._demander('1.0.0').json()

        self.assertTrue(donnees['mise_a_jour_disponible'])
        self.assertEqual(donnees['version'], '9.9.9')
        self.assertEqual(donnees['sha256'], 'b' * 64)
        self.assertTrue(donnees['url'].startswith('https://'))

    def test_sans_identifiants_le_flux_reste_ferme(self):
        self._publier()
        reponse = self.client.get(self.url, {'version': '1.0.0'})
        self.assertEqual(reponse.status_code, 401)

    def test_un_poste_revoque_ne_recoit_plus_de_mise_a_jour(self):
        """
        Le poste revoque perd la synchronisation ; il doit perdre en meme temps
        le canal par lequel on lui installe du logiciel.
        """
        self._publier()
        self.device.actif = False
        self.device.save(update_fields=['actif'])

        self.assertEqual(self._demander('1.0.0').status_code, 403)

    def test_aucune_version_publiee_ne_casse_pas_la_reponse(self):
        donnees = self._demander('1.0.0').json()
        self.assertTrue(donnees['ok'])
        self.assertFalse(donnees['mise_a_jour_disponible'])


class TelechargementMiseAJourTests(TestCase):
    """La partie qui manipule un executable : rien ne passe sans empreinte."""

    def setUp(self):
        self.dossier = tempfile.TemporaryDirectory()
        self.addCleanup(self.dossier.cleanup)
        patch = mock.patch.object(
            auto_mise_a_jour, '_dossier_mises_a_jour', return_value=self.dossier.name,
        )
        patch.start()
        self.addCleanup(patch.stop)

    def _contenu(self, octets=b'installateur-factice'):
        return octets, hashlib.sha256(octets).hexdigest()

    def _reponse_serveur(self, empreinte, version='9.9.9'):
        return {
            'ok': True, 'mise_a_jour_disponible': True, 'version': version,
            'url': 'https://exemple.test/setup.exe', 'sha256': empreinte,
            'taille_octets': None, 'notes': '', 'obligatoire': False,
        }

    def _faux_telechargement(self, octets):
        def telecharger(url, destination, taille_attendue=None):
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with open(destination, 'wb') as fichier:
                fichier.write(octets)
            return len(octets)
        return telecharger

    def _preparer(self, octets, empreinte_annoncee, version='9.9.9'):
        with mock.patch.object(auto_mise_a_jour, '_config',
                               return_value=('https://serveur', 'appareil', 'jeton')), \
                mock.patch.object(auto_mise_a_jour, '_demander_derniere_version',
                                  return_value=self._reponse_serveur(empreinte_annoncee, version)), \
                mock.patch.object(auto_mise_a_jour, '_telecharger',
                                  side_effect=self._faux_telechargement(octets)):
            return auto_mise_a_jour.preparer_mise_a_jour()

    def test_une_version_conforme_est_preparee(self):
        octets, empreinte = self._contenu()

        version = self._preparer(octets, empreinte)

        self.assertEqual(version, '9.9.9')
        descripteur = auto_mise_a_jour.mise_a_jour_en_attente()
        self.assertEqual(descripteur['version'], '9.9.9')
        self.assertTrue(os.path.isfile(descripteur['chemin']))

    def test_une_empreinte_qui_ne_correspond_pas_supprime_le_fichier(self):
        """
        Le fichier recu n'est pas celui annonce : il ne doit ni etre installe,
        ni rester sur le disque a portee d'un double-clic.
        """
        octets, _ = self._contenu()

        version = self._preparer(octets, 'c' * 64)

        self.assertIsNone(version)
        self.assertIsNone(auto_mise_a_jour.mise_a_jour_en_attente())
        restants = [n for n in os.listdir(self.dossier.name) if n.endswith('.exe')]
        self.assertEqual(restants, [])

    def test_un_fichier_altere_apres_coup_n_est_pas_installe(self):
        """
        L'empreinte est reverifiee juste avant le lancement : c'est la, et non
        au telechargement, que le fichier devient du code execute.
        """
        octets, empreinte = self._contenu()
        self._preparer(octets, empreinte)
        descripteur = auto_mise_a_jour.mise_a_jour_en_attente()

        with open(descripteur['chemin'], 'wb') as fichier:
            fichier.write(b'autre-chose')

        self.assertIsNone(auto_mise_a_jour.mise_a_jour_en_attente())
        self.assertFalse(os.path.exists(descripteur['chemin']))

    def test_une_version_deja_installee_est_oubliee(self):
        octets, empreinte = self._contenu()
        self._preparer(octets, empreinte, version=APP_VERSION)

        self.assertIsNone(auto_mise_a_jour.mise_a_jour_en_attente())

    def test_une_adresse_non_chiffree_est_refusee_au_telechargement(self):
        with self.assertRaises(ValueError):
            auto_mise_a_jour._telecharger(
                'http://exemple.test/setup.exe',
                os.path.join(self.dossier.name, 'setup.exe'),
            )

    def test_rien_n_est_tente_sans_configuration(self):
        with mock.patch.object(auto_mise_a_jour, '_config', return_value=None):
            self.assertIsNone(auto_mise_a_jour.preparer_mise_a_jour())

    def test_le_demarrage_lance_l_installateur_puis_oublie_le_descripteur(self):
        """
        Le descripteur est retire avant meme de savoir si l'installation
        reussit : sinon un installateur defaillant serait relance a chaque
        demarrage, et l'application ne s'ouvrirait plus jamais.
        """
        octets, empreinte = self._contenu()
        self._preparer(octets, empreinte)

        with mock.patch.object(auto_mise_a_jour.sys, 'platform', 'win32'), \
                mock.patch.object(auto_mise_a_jour.subprocess, 'Popen') as lancement:
            self.assertTrue(auto_mise_a_jour.appliquer_si_en_attente())

        arguments = lancement.call_args.args[0]
        self.assertIn('/SILENT', arguments)
        self.assertIn('/RELANCE=1', arguments)
        self.assertIsNone(auto_mise_a_jour.mise_a_jour_en_attente())

    def test_sans_mise_a_jour_le_demarrage_continue_normalement(self):
        self.assertFalse(auto_mise_a_jour.appliquer_si_en_attente())

    def test_un_descripteur_illisible_ne_bloque_pas_le_demarrage(self):
        with open(auto_mise_a_jour._fichier_descripteur(), 'w', encoding='utf-8') as fichier:
            fichier.write('{ ceci n est pas du json')

        self.assertFalse(auto_mise_a_jour.appliquer_si_en_attente())


class CoherenceVersionTests(TestCase):
    """Le numero doit rester le meme partout, sinon la mise a jour boucle."""

    def test_l_installateur_porte_la_meme_version_que_l_application(self):
        """
        Si l'installateur annoncait un autre numero, le poste installerait la
        mise a jour puis continuerait a la reclamer : chaque demarrage
        relancerait le meme installateur, indefiniment.
        """
        import re
        from pathlib import Path

        chemin = Path(__file__).resolve().parent.parent / 'installer_myschool.iss'
        contenu = chemin.read_text(encoding='utf-8-sig')
        trouve = re.search(r'#define MyAppVersion "([^"]+)"', contenu)

        self.assertIsNotNone(trouve, "'#define MyAppVersion' absent de l'installateur")
        self.assertEqual(trouve.group(1), APP_VERSION)
