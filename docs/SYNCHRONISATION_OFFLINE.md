# Synchronisation offline / online

## 1. Configurer le serveur PythonAnywhere

Dans PythonAnywhere, ajoute si necessaire une variable d'environnement secrete
reservee aux scripts d'administration :

```text
MYSCHOOL_SYNC_ADMIN_TOKEN=une-longue-cle-secrete
```

Garde aussi :

```text
MYSCHOOL_SYNC_SERVER_URL=https://www.lesjardinswosewa.com
```

## 2. Préparer automatiquement un poste depuis l'administration

1. Ouvrir **Administration Django > Écoles**.
2. Sur la ligne de l'école, cliquer sur **Configurer la version hors ligne**.
3. Donner un nom distinct au poste, par exemple `Poste direction`.
4. Cliquer sur **Créer et télécharger la configuration**.
5. Conserver le fichier téléchargé sous le nom exact `sync_config.json`.
6. Placer ce fichier à côté de `MySchoolGN_Setup_v1.2.1_Generic.exe`.
7. Lancer l'installateur, puis MySchoolGN.

L'installateur copie automatiquement la configuration personnalisée. Au premier
démarrage connecté, la base locale est créée puis limitée à l'école choisie.
Le jeton d'administration du serveur n'est jamais installé sur le poste client.

Le fichier contient :

```json
{
  "MYSCHOOL_SYNC_SERVER_URL": "https://www.lesjardinswosewa.com",
  "MYSCHOOL_SYNC_ECOLE_ID": 1,
  "MYSCHOOL_SYNC_DEVICE_ID": "...",
  "MYSCHOOL_SYNC_TOKEN": "...",
  "MYSCHOOL_SYNC_INTERVAL": 10,
  "MYSCHOOL_SYNC_FAST_INTERVAL": 2
}
```

Le token n'est disponible que dans ce téléchargement. Ne pas envoyer ce fichier
par un canal public. En cas de perte ou de vol, revenir sur la même page et
cliquer sur **Révoquer**, puis créer une nouvelle configuration.

## 3. Configuration manuelle pour un technicien

La commande suivante reste disponible pour les installations sans interface :

```bash
python manage.py register_sync_device --nom "Direction"
```

Copier les valeurs obtenues dans `.env` ou `sync_config.json` sur le poste.

## 4. Synchroniser manuellement

Sur le poste offline :

```bash
python manage.py sync_offline
```

Pour la premiere synchronisation d'un poste nouvellement installe :

```bash
python manage.py sync_offline --initial
```

Pour recevoir seulement les changements :

```bash
python manage.py sync_offline --pull-only
```

Pour envoyer seulement les changements locaux :

```bash
python manage.py sync_offline --push-only
```

Pour reprendre apres un changement serveur connu :

```bash
python manage.py sync_offline --since-id 123
```

## 5. Cadence de la synchronisation

La propagation ne repose pas sur une simple attente : elle combine trois
mecanismes.

| Etape | Delai | Reglage |
|---|---|---|
| Envoi d'une saisie locale | immediat (≈1 s de regroupement) | aucun |
| Detection de ce qui vient des autres postes, en periode d'activite | `MYSCHOOL_SYNC_FAST_INTERVAL` (2 s par defaut) | par poste |
| Detection au repos (plus rien n'a circule depuis 2 minutes) | `MYSCHOOL_SYNC_INTERVAL` (10 s par defaut, plafonne a 15 s) | par poste |
| Rafraichissement de la page ouverte a l'ecran | 3 s | interne |

Une saisie faite sur un poste apparait donc sur les autres en **quelques
secondes**, ecran compris.

Ces verifications ne coutent presque rien : tant que rien n'a change, le poste
ne demande qu'un repere (`/api/v1/sync/state/`), pas les donnees. Le
telechargement complet n'a lieu que lorsque ce repere a bouge.

Le plafond de 15 secondes s'applique meme si un ancien `sync_config.json`
indique une valeur plus grande : les postes deja installes redeviennent
reactifs sans avoir a reinstaller leur configuration.

## 6. Verifier qu'un poste est bien synchronise

```bash
curl -H "X-Sync-Device: VOTRE_DEVICE_ID" -H "X-Sync-Token: VOTRE_TOKEN"   https://www.lesjardinswosewa.com/api/v1/sync/state/
```

La reponse donne `last_change_id`, le numero du dernier changement connu du
serveur pour cette ecole. Il doit avancer des qu'une saisie est faite sur
n'importe quel poste. Dans l'administration, la colonne **Derniere connexion**
de la page *Configurer la version hors ligne* indique si le poste dialogue
toujours avec le serveur.

## Notes importantes

- Chaque poste offline doit avoir son propre `MYSCHOOL_SYNC_DEVICE_ID` et `MYSCHOOL_SYNC_TOKEN`.
- L'installateur generique ne contient le token d'aucune ecole.
- Un appareil revoque ne peut plus envoyer ni recevoir de donnees.
- Les changements sont echanges via `/api/v1/sync/push/` et `/api/v1/sync/pull/`.
- Un ajout part **immediatement** : l'enregistrement reveille la
  synchronisation, sans attendre la fin du cycle en cours.
- Hors-ligne, le poste reessaie de lui-meme et rattrape tout son retard des que
  la connexion Internet revient.
