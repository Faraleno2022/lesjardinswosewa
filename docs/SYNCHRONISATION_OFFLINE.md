# Synchronisation offline / online

## 1. Configurer le serveur Render

Dans Render, ajoute une variable d'environnement secrete :

```text
MYSCHOOL_SYNC_ADMIN_TOKEN=une-longue-cle-secrete
```

Garde aussi :

```text
MYSCHOOL_SYNC_SERVER_URL=https://gs-hadja-kanfing-dian.onrender.com
```

## 2. Enregistrer un poste offline

Sur chaque poste local/offline, mets d'abord dans `.env` :

```text
MYSCHOOL_SYNC_SERVER_URL=https://gs-hadja-kanfing-dian.onrender.com
MYSCHOOL_SYNC_ADMIN_TOKEN=la-meme-cle-que-sur-render
MYSCHOOL_SYNC_ECOLE_ID=1
```

Puis lance :

```bash
python manage.py register_sync_device --nom "Direction"
```

La commande affiche :

```text
MYSCHOOL_SYNC_DEVICE_ID=...
MYSCHOOL_SYNC_TOKEN=...
MYSCHOOL_SYNC_ECOLE_ID=...
```

Copie ces valeurs dans le `.env` du poste offline. Le token n'est affiche qu'une seule fois.

## 3. Synchroniser

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
- Les changements sont echanges via `/api/v1/sync/push/` et `/api/v1/sync/pull/`.
- Cette base configure le transport entre versions offline. L'application progressive des payloads aux modeles metier peut etre ajoutee modele par modele.
