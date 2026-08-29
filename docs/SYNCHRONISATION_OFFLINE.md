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
6. Placer ce fichier à côté de
   `MySchoolGN_Setup_v1.3.5_LesJardinsWosewa.exe`.
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
| Detection au repos (plus rien n'a circule depuis 2 minutes) | `MYSCHOOL_SYNC_INTERVAL` (10 s par defaut, **plafonne a 3 s**) | par poste |
| Rafraichissement de la page ouverte a l'ecran | 3 s | interne |

Une saisie faite sur un poste apparait donc sur les autres en **quelques
secondes**, ecran compris — au repos comme en pleine activite.

Ces verifications ne coutent presque rien : tant que rien n'a change, le poste
ne demande qu'un repere (`/api/v1/sync/state/`), pas les donnees. C'est une
requete sans corps, dont la reponse tient en trois nombres, et cote serveur un
`MAX(id)` sur une colonne indexee. Rien la-dedans ne justifiait de faire
attendre quinze secondes une donnee saisie ailleurs : le plafond au repos est
donc de **3 secondes**. Le telechargement complet n'a lieu que lorsque le
repere a bouge.

Ce plafond s'applique meme si un ancien `sync_config.json` indique une valeur
plus grande : les postes deja installes redeviennent reactifs sans avoir a
reinstaller leur configuration.

### Rattrapage apres une coupure

Le serveur ne sert que 200 changements par requete. Un poste rentre apres
plusieurs jours hors ligne **enchaine les lots dans le meme cycle** (jusqu'a
25, soit 5 000 changements), au lieu d'en descendre 200 toutes les deux
secondes. Le reste suit au cycle suivant. Sans cela, un retard de quelques
milliers de changements se rattrapait en plusieurs minutes, pendant lesquelles
les ecrans affichaient des donnees incompletes.

Le meme enchainement s'applique a l'envoi. Un changement refuse par le serveur
n'est represente qu'au cycle **suivant**, jamais dans le meme : son budget de
tentatives est prevu pour laisser le temps a une dependance manquante
d'arriver, et le consommer d'un coup ferait abandonner une donnee qui serait
passee.

### Compression

Les lots transportent le contenu des fichiers (photos d'eleves encodees en
base64) : une reponse se compte en megaoctets. Les echanges sont compresses
(`Accept-Encoding: gzip`), ce qui divise le temps de descente par plusieurs sur
les liaisons dont dispose une ecole. Un serveur ancien qui ne compresse pas
reste compris : la reponse est lue telle quelle.

## 6. Verifier qu'un poste est bien synchronise

```bash
curl -H "X-Sync-Device: VOTRE_DEVICE_ID" -H "X-Sync-Token: VOTRE_TOKEN"   https://www.lesjardinswosewa.com/api/v1/sync/state/
```

La reponse donne `last_change_id`, le numero du dernier changement connu du
serveur pour cette ecole. Il doit avancer des qu'une saisie est faite sur
n'importe quel poste. Dans l'administration, la colonne **Derniere connexion**
de la page *Configurer la version hors ligne* indique si le poste dialogue
toujours avec le serveur.

Si cette colonne affiche **Jamais** alors que le poste est installe et lance
depuis un moment, la synchronisation n'a encore jamais reussi une seule fois :
voir la section suivante.

## 7. Diagnostiquer un poste qui ne synchronise pas

Le worker en arriere-plan reessaie en silence quand il echoue, ce qui rend un
poste bloque difficile a diagnostiquer a distance. Deux outils y remedient.

**Diagnostic immediat**, a executer directement sur le poste concerne
(ferme l'application au besoin, puis depuis une invite dans le dossier
d'installation) :

```bash
MySchoolGN.exe --diagnostiquer-sync
```

Cette commande declenche un seul cycle de synchronisation et affiche
immediatement, en clair, ce que le worker mettrait sinon plusieurs minutes a
tracer dans le journal : serveur contacte, resultat, et en cas d'echec le
type d'exception avec une cause probable (jeton revoque, certificat HTTPS non
reconnu, reseau bloque...).

**Journal du poste** (`myschool.log`, a cote de l'exe) : depuis la version
1.3.1, chaque echec de synchronisation y laisse une trace — le tout premier
immediatement, les suivants au plus toutes les 5 minutes tant que ca persiste
— ainsi qu'un message quand la connexion revient.

**Cause frequente sur un poste d'ecole ou de bureau** : un pare-feu ou un
antivirus qui inspecte le trafic HTTPS avec son propre certificat. Windows
(et donc un navigateur) lui fait confiance, mais l'application, qui embarque
son propre lot de certificats, non — toute connexion au serveur echoue alors
des le depart, silencieusement avant la version 1.3.1. Depuis cette version,
l'application verifie les certificats HTTPS via le magasin de Windows
(bibliotheque `truststore`), ce qui aligne son comportement sur celui d'un
navigateur.

## Notes importantes

- Chaque poste offline doit avoir son propre `MYSCHOOL_SYNC_DEVICE_ID` et `MYSCHOOL_SYNC_TOKEN`.
- L'installateur generique ne contient le token d'aucune ecole.
- Un appareil revoque ne peut plus envoyer ni recevoir de donnees.
- Les changements sont echanges via `/api/v1/sync/push/` et `/api/v1/sync/pull/`.
- Un ajout part **immediatement** : l'enregistrement reveille la
  synchronisation, sans attendre la fin du cycle en cours.
- Hors-ligne, le poste reessaie de lui-meme et rattrape tout son retard des que
  la connexion Internet revient.
