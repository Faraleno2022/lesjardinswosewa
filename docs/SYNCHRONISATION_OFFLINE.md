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
6. Placer ce fichier à côté de `MySchoolGN_Setup_v1.2.0_Generic.exe`.
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
  "MYSCHOOL_SYNC_INTERVAL": 60
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

## Notes importantes

- Chaque poste offline doit avoir son propre `MYSCHOOL_SYNC_DEVICE_ID` et `MYSCHOOL_SYNC_TOKEN`.
- L'installateur generique ne contient le token d'aucune ecole.
- Un appareil revoque ne peut plus envoyer ni recevoir de donnees.
- Les changements sont echanges via `/api/v1/sync/push/` et `/api/v1/sync/pull/`.
- L'application tente automatiquement une synchronisation toutes les 60 secondes
  et reprend lorsque la connexion Internet revient.
