"""Sauvegarde et restauration de l'installation locale (version installable).

Règle 3-2-1 : chaque archive part vers PLUSIEURS destinations — typiquement un
dossier synchronisé dans le cloud (copie hors site) et un support amovible
laissé sur place (copie hors ligne, disponible même sans Internet). Les deux
sont détectés automatiquement : aucune configuration n'est nécessaire sur un
poste ordinaire.

Une archive contient la base de données, le dossier `media/` (photos, pièces
justificatives) et un manifeste décrivant son contenu. Elle se restaure sur une
machine neuve sans rien d'autre.

Points de conception importants :

- La base SQLite n'est JAMAIS copiée comme un fichier ordinaire : une copie
  faite pendant que l'application écrit produit une archive corrompue, ce qui
  ne se découvre que le jour de la restauration. On passe par l'API de
  sauvegarde en ligne de SQLite (`Connection.backup`), conçue pour cela.
- Le module ne dépend pas de Django : il est importable depuis `run_server.py`
  (donc depuis l'exécutable PyInstaller) comme depuis une commande de
  management, sans que la découverte des commandes soit en jeu.
- Rotation grand-père/père/fils : sans elle, une corruption découverte trois
  semaines plus tard trouve toutes les archives déjà écrasées.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timedelta

# ─── Constantes ───────────────────────────────────────────────────────────────

PREFIXE = 'myschoolgn_sauvegarde_'
HORODATAGE = '%Y%m%d_%H%M%S'
NOM_MANIFESTE = 'manifeste.json'
NOM_BASE_DANS_ARCHIVE = 'db.sqlite3'
DOSSIER_MEDIA_DANS_ARCHIVE = 'media'
DOSSIER_LOCAL_DEFAUT = 'sauvegardes'

# Rotation : nombre d'archives conservées par destination.
GARDER_QUOTIDIENNES = 7
GARDER_HEBDOMADAIRES = 4
GARDER_MENSUELLES = 12

# Dossiers de `media/` exclus : contenus reconstructibles, inutiles à sauvegarder.
MEDIA_EXCLUS = {'tmp', 'cache', 'temp'}

DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3


# ─── Rapport d'exécution ──────────────────────────────────────────────────────

@dataclass
class Rapport:
    """Résultat d'une sauvegarde, destiné au journal et à l'affichage."""

    archive: str = ''
    taille: int = 0
    destinations_ok: list = field(default_factory=list)
    destinations_ko: list = field(default_factory=list)
    supprimees: list = field(default_factory=list)
    chiffree: bool = False
    avertissements: list = field(default_factory=list)
    erreur: str = ''

    @property
    def succes(self) -> bool:
        """Une sauvegarde réussit dès qu'une destination a reçu l'archive."""
        return not self.erreur and bool(self.destinations_ok)

    def resume(self) -> str:
        if self.erreur:
            return f'ECHEC : {self.erreur}'
        taille_mo = self.taille / (1024 * 1024)
        texte = (f'{os.path.basename(self.archive)} ({taille_mo:.1f} Mo) -> '
                 f'{len(self.destinations_ok)} destination(s)')
        if self.destinations_ko:
            texte += f', {len(self.destinations_ko)} en echec'
        return texte


# ─── Chemins de l'installation ────────────────────────────────────────────────

def base_dir() -> str:
    """Dossier de l'installation, tel que posé par run_server.py."""
    depuis_env = os.environ.get('MYSCHOOL_BASE_DIR')
    if depuis_env and os.path.isdir(depuis_env):
        return depuis_env
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chemin_base_donnees() -> str:
    return os.path.join(base_dir(), 'db.sqlite3')


def chemin_media() -> str:
    return os.path.join(base_dir(), 'media')


def _journal(message: str) -> None:
    """Trace une ligne dans logs/sauvegarde.log, sans jamais faire échouer l'appelant."""
    try:
        dossier = os.path.join(base_dir(), 'logs')
        os.makedirs(dossier, exist_ok=True)
        horodatage = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(os.path.join(dossier, 'sauvegarde.log'), 'a', encoding='utf-8') as f:
            f.write(f'{horodatage}  {message}\n')
    except Exception:
        pass


# ─── Configuration ────────────────────────────────────────────────────────────

def charger_config() -> dict:
    """Réglages du poste, lus dans `sauvegarde_config.json`.

    Même convention que `sync_config.json` : à côté de l'exécutable, ou dans
    %APPDATA%\\MySchoolGN. Toutes les clés sont facultatives ; sans fichier, la
    détection automatique fait le travail.
    """
    candidats = [
        os.path.join(base_dir(), 'sauvegarde_config.json'),
        os.path.join(os.environ.get('APPDATA', ''), 'MySchoolGN', 'sauvegarde_config.json'),
    ]
    for chemin in candidats:
        try:
            if chemin and os.path.exists(chemin):
                with open(chemin, 'r', encoding='utf-8') as f:
                    donnees = json.load(f)
                if isinstance(donnees, dict):
                    return donnees
        except Exception as err:
            _journal(f'Configuration illisible ({chemin}) : {err}')
    return {}


# ─── Détection des destinations ───────────────────────────────────────────────

def _dossiers_cloud() -> list:
    """Dossiers de synchronisation cloud présents sur la machine.

    OneDrive et Dropbox exposent une variable d'environnement ; Google Drive
    (Drive pour ordinateur) monte une lettre de lecteur ou un dossier du profil.
    """
    trouves = []
    profil = os.environ.get('USERPROFILE', '')

    for variable in ('OneDrive', 'OneDriveCommercial', 'OneDriveConsumer', 'Dropbox'):
        chemin = os.environ.get(variable)
        if chemin and os.path.isdir(chemin):
            trouves.append(chemin)

    if profil:
        for nom in ('OneDrive', 'Google Drive', 'Mon Drive', 'Dropbox', 'iCloudDrive'):
            chemin = os.path.join(profil, nom)
            if os.path.isdir(chemin):
                trouves.append(chemin)

    # Google Drive pour ordinateur : lettre dédiée contenant « Mon Drive »
    for lettre in _lettres_lecteurs():
        for nom in ('Mon Drive', 'My Drive'):
            chemin = os.path.join(lettre, nom)
            if os.path.isdir(chemin):
                trouves.append(chemin)

    # Dédoublonnage en conservant l'ordre de découverte
    uniques = []
    for chemin in trouves:
        reel = os.path.normpath(chemin)
        if reel not in uniques:
            uniques.append(reel)
    return uniques


def _lettres_lecteurs() -> list:
    """Lettres de lecteurs présentes (Windows) ; liste vide ailleurs."""
    if os.name != 'nt':
        return []
    try:
        masque = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return []
    return [f'{chr(65 + i)}:\\' for i in range(26) if masque & (1 << i)]


def _supports_amovibles() -> list:
    """Clés USB et disques externes actuellement branchés."""
    if os.name != 'nt':
        return []
    resultats = []
    for lettre in _lettres_lecteurs():
        if lettre.upper().startswith('C:'):
            continue
        try:
            type_lecteur = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(lettre))
        except Exception:
            continue
        # Un disque externe USB est vu comme FIXED : on l'accepte aussi, car
        # c'est un support « laissé sur place » tout aussi valable qu'une clé.
        if type_lecteur in (DRIVE_REMOVABLE, DRIVE_FIXED) and os.path.isdir(lettre):
            resultats.append(lettre)
    return resultats


def destinations(config: dict | None = None) -> list:
    """Destinations retenues pour cette sauvegarde, dans l'ordre de priorité.

    Toujours au moins le dossier local `sauvegardes/` : il garantit qu'une
    archive existe même si le cloud est absent et qu'aucune clé n'est branchée.
    Les chemins déclarés dans la configuration remplacent la détection.
    """
    config = config if config is not None else charger_config()
    declarees = config.get('MYSCHOOL_SAUVEGARDE_DESTINATIONS')
    if isinstance(declarees, str):
        declarees = [declarees]

    if declarees:
        retenues = [os.path.normpath(str(d)) for d in declarees if str(d).strip()]
    else:
        retenues = [os.path.join(base_dir(), DOSSIER_LOCAL_DEFAUT)]
        sous_dossier = str(config.get('MYSCHOOL_SAUVEGARDE_SOUS_DOSSIER')
                           or 'Sauvegardes MySchoolGN')
        for racine in _dossiers_cloud():
            retenues.append(os.path.join(racine, sous_dossier))
        for support in _supports_amovibles():
            retenues.append(os.path.join(support, sous_dossier))

    uniques = []
    for chemin in retenues:
        if chemin not in uniques:
            uniques.append(chemin)
    return uniques


# ─── Fabrication de l'archive ─────────────────────────────────────────────────

def _copier_base(source: str, cible: str) -> None:
    """Copie cohérente de la base, application ouverte ou fermée.

    `Connection.backup` est l'API de sauvegarde en ligne de SQLite : elle prend
    un instantané cohérent même si des écritures ont lieu pendant la copie.
    """
    connexion_source = sqlite3.connect(f'file:{source}?mode=ro', uri=True)
    try:
        connexion_cible = sqlite3.connect(cible)
        try:
            connexion_source.backup(connexion_cible)
        finally:
            connexion_cible.close()
    finally:
        connexion_source.close()


def _empreinte(chemin: str) -> str:
    condensat = hashlib.sha256()
    with open(chemin, 'rb') as f:
        for bloc in iter(lambda: f.read(1024 * 1024), b''):
            condensat.update(bloc)
    return condensat.hexdigest()


def _fichiers_media() -> list:
    """Fichiers de `media/` à embarquer, avec leur chemin relatif."""
    racine = chemin_media()
    if not os.path.isdir(racine):
        return []
    fichiers = []
    for dossier, sous_dossiers, noms in os.walk(racine):
        sous_dossiers[:] = [d for d in sous_dossiers if d.lower() not in MEDIA_EXCLUS]
        for nom in noms:
            absolu = os.path.join(dossier, nom)
            fichiers.append((absolu, os.path.relpath(absolu, racine)))
    return fichiers


def _statistiques_base(chemin: str) -> dict:
    """Quelques compteurs métier, pour reconnaître une archive au premier coup d'œil."""
    compteurs = {}
    tables = {
        'eleves': 'eleves_eleve',
        'paiements': 'paiements_paiement',
        'entrees_recouvrement': 'depenses_entree',
    }
    try:
        connexion = sqlite3.connect(f'file:{chemin}?mode=ro', uri=True)
        try:
            for cle, table in tables.items():
                try:
                    curseur = connexion.execute(f'SELECT COUNT(*) FROM {table}')
                    compteurs[cle] = curseur.fetchone()[0]
                except sqlite3.Error:
                    continue
        finally:
            connexion.close()
    except sqlite3.Error:
        pass
    return compteurs


def _ouvrir_zip(chemin: str, mot_de_passe: str):
    """Ouvre l'archive en écriture, chiffrée si un mot de passe est fourni.

    Le chiffrement AES exige `pyzipper`, absent du socle : sans lui on écrit une
    archive claire plutôt que d'échouer, et on le signale. Une sauvegarde en
    clair vaut mieux que pas de sauvegarde — mais elle contient des données
    personnelles d'élèves, d'où l'avertissement.
    """
    if mot_de_passe:
        try:
            import pyzipper
            archive = pyzipper.AESZipFile(
                chemin, 'w', compression=pyzipper.ZIP_DEFLATED,
                encryption=pyzipper.WZ_AES,
            )
            archive.setpassword(mot_de_passe.encode('utf-8'))
            return archive, True, ''
        except ImportError:
            avertissement = ("Chiffrement ignoré : le module pyzipper n'est pas "
                             "installé. L'archive contient des données personnelles "
                             "en clair — protégez le support (BitLocker).")
        except Exception as err:
            avertissement = f'Chiffrement impossible ({err}) : archive écrite en clair.'
    else:
        avertissement = ''
    return zipfile.ZipFile(chemin, 'w', compression=zipfile.ZIP_DEFLATED), False, avertissement


def creer_archive(dossier_sortie: str, mot_de_passe: str = '') -> tuple:
    """Fabrique l'archive dans `dossier_sortie`. Retourne (chemin, avertissements)."""
    os.makedirs(dossier_sortie, exist_ok=True)
    horodatage = datetime.now().strftime(HORODATAGE)
    chemin_archive = os.path.join(dossier_sortie, f'{PREFIXE}{horodatage}.zip')
    avertissements = []

    with tempfile.TemporaryDirectory(prefix='myschool_sauv_') as travail:
        copie_base = os.path.join(travail, NOM_BASE_DANS_ARCHIVE)
        _copier_base(chemin_base_donnees(), copie_base)

        manifeste = {
            'format': 1,
            'application': 'MySchoolGN',
            'date': datetime.now().isoformat(timespec='seconds'),
            'machine': os.environ.get('COMPUTERNAME', ''),
            'utilisateur': os.environ.get('USERNAME', ''),
            'base': {
                'nom': NOM_BASE_DANS_ARCHIVE,
                'taille': os.path.getsize(copie_base),
                'sha256': _empreinte(copie_base),
            },
            'statistiques': _statistiques_base(copie_base),
        }

        fichiers = _fichiers_media()
        manifeste['media'] = {'nombre': len(fichiers),
                              'taille': sum(os.path.getsize(a) for a, _ in fichiers)}

        archive, chiffree, avertissement = _ouvrir_zip(chemin_archive, mot_de_passe)
        if avertissement:
            avertissements.append(avertissement)
        manifeste['chiffree'] = chiffree
        try:
            archive.writestr(NOM_MANIFESTE, json.dumps(manifeste, ensure_ascii=False, indent=2))
            archive.write(copie_base, NOM_BASE_DANS_ARCHIVE)
            for absolu, relatif in fichiers:
                try:
                    archive.write(absolu, f'{DOSSIER_MEDIA_DANS_ARCHIVE}/{relatif}')
                except OSError as err:
                    avertissements.append(f'Fichier ignoré ({relatif}) : {err}')
        finally:
            archive.close()

    return chemin_archive, avertissements


# ─── Rotation ─────────────────────────────────────────────────────────────────

def _date_archive(nom: str):
    if not nom.startswith(PREFIXE) or not nom.endswith('.zip'):
        return None
    try:
        return datetime.strptime(nom[len(PREFIXE):-4], HORODATAGE)
    except ValueError:
        return None


def archives_a_conserver(dates: list) -> set:
    """Sélection grand-père/père/fils : la plus récente de chaque période gardée.

    Toutes les archives des `GARDER_QUOTIDIENNES` derniers jours sont
    conservées, puis une par semaine, puis une par mois. Le reste est effaçable.
    """
    if not dates:
        return set()
    reference = max(dates)
    limite_quotidienne = reference - timedelta(days=GARDER_QUOTIDIENNES)
    a_garder = {d for d in dates if d >= limite_quotidienne}

    def derniere_par(cle, combien):
        groupes = {}
        for date in dates:
            groupes.setdefault(cle(date), []).append(date)
        for _, membres in sorted(groupes.items(), reverse=True)[:combien]:
            a_garder.add(max(membres))

    derniere_par(lambda d: d.isocalendar()[:2], GARDER_HEBDOMADAIRES)
    derniere_par(lambda d: (d.year, d.month), GARDER_MENSUELLES)
    return a_garder


def appliquer_rotation(dossier: str) -> list:
    """Supprime les archives hors politique. Retourne les noms supprimés."""
    try:
        noms = os.listdir(dossier)
    except OSError:
        return []

    par_date = {}
    for nom in noms:
        date = _date_archive(nom)
        if date:
            par_date[date] = nom

    a_garder = archives_a_conserver(list(par_date))
    supprimees = []
    for date, nom in sorted(par_date.items()):
        if date in a_garder:
            continue
        try:
            os.remove(os.path.join(dossier, nom))
            supprimees.append(nom)
        except OSError as err:
            _journal(f'Suppression impossible ({nom}) : {err}')
    return supprimees


# ─── Sauvegarde ───────────────────────────────────────────────────────────────

def executer_sauvegarde(destinations_demandees=None, mot_de_passe=None,
                        config: dict | None = None) -> Rapport:
    """Fabrique une archive et la dépose sur chaque destination, puis fait le tri.

    L'échec d'une destination (clé débranchée, cloud saturé) n'empêche pas les
    autres : c'est tout l'intérêt d'en avoir plusieurs.
    """
    config = config if config is not None else charger_config()
    rapport = Rapport()

    base = chemin_base_donnees()
    if not os.path.exists(base):
        rapport.erreur = f'Base de données introuvable : {base}'
        _journal(rapport.resume())
        return rapport

    cibles = destinations_demandees or destinations(config)
    if not cibles:
        rapport.erreur = 'Aucune destination de sauvegarde disponible.'
        _journal(rapport.resume())
        return rapport

    if mot_de_passe is None:
        mot_de_passe = str(config.get('MYSCHOOL_SAUVEGARDE_MOT_DE_PASSE') or '')

    with tempfile.TemporaryDirectory(prefix='myschool_archive_') as travail:
        try:
            archive, avertissements = creer_archive(travail, mot_de_passe)
        except Exception as err:
            rapport.erreur = f"Création de l'archive impossible : {err}"
            _journal(rapport.resume())
            return rapport

        rapport.archive = archive
        rapport.taille = os.path.getsize(archive)
        rapport.avertissements.extend(avertissements)
        rapport.chiffree = bool(mot_de_passe) and not any(
            'Chiffrement' in a for a in avertissements)

        for cible in cibles:
            try:
                os.makedirs(cible, exist_ok=True)
                shutil.copy2(archive, os.path.join(cible, os.path.basename(archive)))
                rapport.destinations_ok.append(cible)
                rapport.supprimees.extend(appliquer_rotation(cible))
            except Exception as err:
                rapport.destinations_ko.append(f'{cible} ({err})')

    if not rapport.destinations_ok:
        rapport.erreur = 'Aucune destination n\'a pu recevoir l\'archive.'

    _journal(rapport.resume())
    for avertissement in rapport.avertissements:
        _journal(f'  Avertissement : {avertissement}')
    for echec in rapport.destinations_ko:
        _journal(f'  Destination en echec : {echec}')
    return rapport


def derniere_sauvegarde(config: dict | None = None):
    """Date de l'archive la plus récente, toutes destinations confondues."""
    dates = []
    for cible in destinations(config):
        try:
            for nom in os.listdir(cible):
                date = _date_archive(nom)
                if date:
                    dates.append(date)
        except OSError:
            continue
    return max(dates) if dates else None


# ─── Restauration ─────────────────────────────────────────────────────────────

def lire_manifeste(archive: str, mot_de_passe: str = '') -> dict:
    """Manifeste d'une archive, sans rien extraire — sert à l'inspecter avant restauration."""
    ouvrir = zipfile.ZipFile
    if mot_de_passe:
        try:
            import pyzipper
            ouvrir = pyzipper.AESZipFile
        except ImportError:
            pass
    with ouvrir(archive) as zf:
        if mot_de_passe:
            zf.setpassword(mot_de_passe.encode('utf-8'))
        return json.loads(zf.read(NOM_MANIFESTE).decode('utf-8'))


def restaurer(archive: str, mot_de_passe: str = '', config: dict | None = None) -> Rapport:
    """Remet en place la base et les médias contenus dans l'archive.

    L'installation existante n'est jamais écrasée sans filet : base et médias
    actuels sont mis de côté sous un nom horodaté avant remplacement. Le
    condensat du manifeste est vérifié — une archive tronquée est refusée ici,
    pas après avoir détruit l'existant.
    """
    rapport = Rapport(archive=archive)
    if not os.path.exists(archive):
        rapport.erreur = f'Archive introuvable : {archive}'
        return rapport

    ouvrir = zipfile.ZipFile
    if mot_de_passe:
        try:
            import pyzipper
            ouvrir = pyzipper.AESZipFile
        except ImportError:
            rapport.avertissements.append(
                "pyzipper absent : une archive chiffrée ne pourra pas être lue.")

    horodatage = datetime.now().strftime(HORODATAGE)
    with tempfile.TemporaryDirectory(prefix='myschool_restaure_') as travail:
        try:
            with ouvrir(archive) as zf:
                if mot_de_passe:
                    zf.setpassword(mot_de_passe.encode('utf-8'))
                manifeste = json.loads(zf.read(NOM_MANIFESTE).decode('utf-8'))
                zf.extractall(travail)
        except Exception as err:
            rapport.erreur = f'Archive illisible : {err}'
            return rapport

        base_extraite = os.path.join(travail, NOM_BASE_DANS_ARCHIVE)
        if not os.path.exists(base_extraite):
            rapport.erreur = "L'archive ne contient pas de base de données."
            return rapport

        attendu = (manifeste.get('base') or {}).get('sha256')
        if attendu and _empreinte(base_extraite) != attendu:
            rapport.erreur = ('Archive corrompue : le condensat de la base ne '
                              'correspond pas au manifeste. Restauration annulée.')
            return rapport

        base_actuelle = chemin_base_donnees()
        if os.path.exists(base_actuelle):
            shutil.move(base_actuelle, f'{base_actuelle}.avant_restauration_{horodatage}')
        shutil.move(base_extraite, base_actuelle)

        media_extrait = os.path.join(travail, DOSSIER_MEDIA_DANS_ARCHIVE)
        if os.path.isdir(media_extrait):
            media_actuel = chemin_media()
            if os.path.isdir(media_actuel):
                shutil.move(media_actuel, f'{media_actuel}_avant_restauration_{horodatage}')
            shutil.move(media_extrait, media_actuel)

        rapport.destinations_ok.append(base_dir())

    _journal(f'Restauration depuis {os.path.basename(archive)} : OK')
    return rapport


def archives_disponibles(config: dict | None = None) -> list:
    """Archives trouvées sur toutes les destinations, la plus récente d'abord."""
    trouvees = []
    for cible in destinations(config):
        try:
            noms = os.listdir(cible)
        except OSError:
            continue
        for nom in noms:
            date = _date_archive(nom)
            if date:
                chemin = os.path.join(cible, nom)
                try:
                    taille = os.path.getsize(chemin)
                except OSError:
                    taille = 0
                trouvees.append({'chemin': chemin, 'date': date, 'taille': taille})
    return sorted(trouvees, key=lambda a: a['date'], reverse=True)
