# Mises a jour automatiques de l'application Windows

Les postes installes chez les utilisateurs recuperent les nouvelles versions
tout seuls. Personne n'a besoin de passer avec une cle USB.

## Comment ca se passe, vu du poste

1. Toutes les 6 heures, le poste demande au serveur en ligne s'il existe une
   version plus recente que la sienne.
2. Si oui, il telecharge l'installateur **en tache de fond**, sans rien
   interrompre.
3. Il verifie l'empreinte SHA-256 du fichier. Si elle ne correspond pas, le
   fichier est supprime et rien ne s'installe.
4. Un bandeau discret annonce a l'ecran que la version est prete.
5. **Au demarrage suivant** de MySchoolGN, l'installateur se lance en mode
   totalement silencieux, sauvegarde la base et la configuration, remplace les
   fichiers, restaure les donnees, puis rouvre l'application.

L'installation attend le redemarrage volontairement : l'installateur doit
fermer l'application pour remplacer son executable, et couper une saisie en
cours coute plus cher que d'attendre quelques heures.

## Publier une nouvelle version

### 1. Compiler

```bash
python build_exe.py
```

Le script recopie d'abord `APP_VERSION` (defini dans
`ecole_moderne/version.py`) dans `installer_myschool.iss`. **Le numero ne se
modifie qu'a un seul endroit** : `ecole_moderne/version.py`.

Compilez ensuite l'installateur avec Inno Setup. Le fichier obtenu s'appelle
`Output/MySchoolGN_Setup_v<version>_Generic.exe`.

### 2. Relever l'empreinte

```bash
python build_exe.py --empreinte
```

Affiche le numero de version, l'empreinte SHA-256 et la taille exacte.
L'equivalent Windows manuel :

```bash
certutil -hashfile Output\MySchoolGN_Setup_v1.3.0_Generic.exe SHA256
```

### 3. Publier la release GitHub

L'installateur ne doit **pas** etre depose sur PythonAnywhere : ni la place ni
la bande passante n'y suffisent. Publiez-le la ou le telechargement est gratuit
et illimite, en *release* GitHub sur le depot
`Faraleno2022/GS_hadja_kanfing_dian-` :

- **tag** : `desktop-v1.3.0` (seuls les nombres comptent, le prefixe est libre) ;
- **fichier joint** : `MySchoolGN_Setup_v1.3.0.exe` ;
- **description** : ce que la version apporte, en clair. Elle est reprise telle
  quelle comme notes de version.

Ni brouillon (*draft*) ni pre-publication (*prerelease*) : ces deux etats
signifient exactement « pas encore pour les postes », et sont ignores.

**Il n'y a pas d'etape 4.** Le serveur lit les publications GitHub et recopie
de lui-meme le numero, l'adresse et l'empreinte SHA-256 dans sa table des
versions — GitHub calcule cette empreinte a la mise en ligne et l'expose dans
son API. Auparavant, il fallait ressaisir ces trois informations a la main, et
une release oubliee restait invisible des postes sans que rien ne le signale.

L'import se declenche quand un poste vient demander s'il existe une mise a
jour, au plus une fois par quart d'heure, et **hors de la requete** : celle-ci
ne doit pas etre retenue le temps d'un aller-retour vers GitHub, qui
immobiliserait l'un des rares processus servant aussi le site public. La
version rapatriee est donc servie a la question suivante du poste.

Pour ne rien laisser dependre du passage des postes, ajoutez une tache
planifiee quotidienne sur PythonAnywhere (onglet **Tasks**) :

```bash
cd ~/lesjardinswosewa && python manage.py importer_versions_github
```

C'est aussi la commande a lancer a la main pour verifier tout de suite qu'une
release fraichement publiee est bien vue :

```bash
python manage.py importer_versions_github
```

Elle affiche ce qu'elle a importe et quelle version sera proposee aux postes.

Une release **sans empreinte publiee** est ignoree, jamais installee a
l'aveugle : le poste telecharge un executable et va le lancer.

### 4. Verifier

```bash
curl -H "X-Sync-Device: VOTRE_DEVICE_ID" -H "X-Sync-Token: VOTRE_TOKEN" \
  "https://www.lesjardinswosewa.com/api/v1/updates/latest/?version=1.2.1"
```

La reponse doit contenir `"mise_a_jour_disponible": true` et le bon numero.

## Revenir en arriere

Decochez *Publiee* sur la version fautive dans **Administration Django >
Versions de l'application**. Les postes qui ne l'ont pas encore telechargee ne
la verront plus, et **l'import GitHub ne la recochera jamais** : c'est le seul
indicateur que l'import ne touche pas, precisement pour que ce geste ne soit
pas annule au quart d'heure suivant. Supprimer la release sur GitHub produit le
meme effet pour les serveurs qui ne l'ont pas encore importee.

Ceux qui l'ont deja installee doivent recevoir une version **superieure**
corrigeant le probleme : republier un ancien numero ne fait pas redescendre les
postes, c'est voulu.

## Quand le serveur est injoignable

Le poste interroge **toujours son serveur en premier** : c'est lui qui porte la
decision, et un « rien de neuf » de sa part est definitif — sinon, depublier
une version defectueuse n'aurait plus aucun effet.

GitHub n'est consulte directement que dans deux cas :

- le serveur n'a pas repondu du tout (panne, reseau coupe cote serveur) ;
- le poste n'a jamais ete relie a un serveur (installation autonome).

Un refus explicite du serveur (`403`, poste revoque) **n'ouvre pas** ce
recours : le serveur a repondu, et sa reponse est que cette machine n'est plus
autorisee. Une version trouvee sur GitHub n'est par ailleurs jamais marquee
*obligatoire* : imposer une installation est une decision du serveur, et un
poste coupe du sien est justement celui a qui on ne veut rien imposer.

## Reglages du serveur

Variables d'environnement, toutes facultatives :

| Variable | Defaut | Role |
|---|---|---|
| `MYSCHOOL_GITHUB_REPO` | `Faraleno2022/GS_hadja_kanfing_dian-` | Depot dont les publications font foi |
| `MYSCHOOL_GITHUB_TOKEN` | vide | Releve le quota de 60 appels/heure/IP, partage sur un hebergement mutualise. Le depot etant public, un jeton n'est pas necessaire |
| `MYSCHOOL_GITHUB_AUTO_IMPORT` | `1` | Mettre a `0` pour n'importer que par la commande |

## Ce qui protege les postes

- L'installateur n'est jamais execute sans que son empreinte SHA-256
  corresponde a celle declaree dans l'administration. La verification a lieu
  deux fois : apres le telechargement, puis **juste avant le lancement** —
  c'est la que le fichier devient du code execute.
- Le serveur et le telechargement n'acceptent que des adresses `https`. Une
  redirection du fichier vers `http` est egalement refusee.
- Le flux des mises a jour utilise les memes identifiants que la
  synchronisation. Un poste revoque perd les deux en meme temps : on ne peut
  pas installer de logiciel sur une machine qui n'est plus autorisee.
- Le descripteur est efface avant le lancement de l'installateur. Si celui-ci
  echoue, le demarrage suivant repart normalement au lieu de relancer sans fin
  le meme fichier.

## Reglage

Dans `sync_config.json` de chaque poste :

```json
{
  "MYSCHOOL_UPDATE_INTERVAL": "21600"
}
```

Intervalle entre deux verifications, en secondes (6 heures par defaut, 10
minutes au minimum). La recherche s'appuie sur `MYSCHOOL_SYNC_SERVER_URL`,
`MYSCHOOL_SYNC_DEVICE_ID` et `MYSCHOOL_SYNC_TOKEN` : un poste non relie au
serveur ne cherche pas de mise a jour.

## Diagnostic sur un poste

- `myschool.log` indique maintenant les refus HTTP (`401`/`403`) et les erreurs
  reseau rencontres pendant la recherche de version.
- `mises_a_jour/en_attente.json` existe quand un installateur verifie attend le
  prochain demarrage.
- `mises_a_jour/installation.log` contient le journal Inno Setup de la derniere
  installation automatique.

Un retour `403 Appareil non autorise` signifie que le poste a ete revoque ou
que son fichier `sync_config.json` ne correspond plus au jeton enregistre sur
le serveur. Il faut alors generer une nouvelle configuration depuis la fiche de
l'ecole ; contourner cette autorisation rendrait les mises a jour dangereuses.
