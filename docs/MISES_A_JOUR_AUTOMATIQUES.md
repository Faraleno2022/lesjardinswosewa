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
   silencieux, remplace les fichiers, puis rouvre l'application.

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

### 3. Heberger le fichier

L'installateur ne doit **pas** etre depose sur PythonAnywhere : ni la place ni
la bande passante n'y suffisent. Publiez-le la ou le telechargement est
gratuit et illimite — une *release* GitHub sur
`github.com/Faraleno2022/lesjardinswosewa` convient. Notez l'adresse directe
du fichier, qui doit etre en **https**.

### 4. Declarer la version

Dans **Administration Django > Versions de l'application > Ajouter** :

| Champ | Valeur |
|---|---|
| Version | `1.3.0` |
| Url telechargement | l'adresse https du `.exe` |
| Sha256 | l'empreinte relevee a l'etape 2 |
| Taille octets | la taille exacte (facultatif, mais recommande) |
| Notes | ce que la version apporte, en clair |
| Obligatoire | a cocher si la version corrige un probleme serieux |
| **Publiee** | **a cocher seulement quand tout est verifie** |

Tant que *Publiee* reste decoche, **aucun poste ne voit la version**. C'est le
filet : on peut tout preparer, tester sur une machine, et ne diffuser qu'apres.

### 5. Verifier

```bash
curl -H "X-Sync-Device: VOTRE_DEVICE_ID" -H "X-Sync-Token: VOTRE_TOKEN" \
  "https://www.lesjardinswosewa.com/api/v1/updates/latest/?version=1.2.1"
```

La reponse doit contenir `"mise_a_jour_disponible": true` et le bon numero.

## Revenir en arriere

Decochez *Publiee* sur la version fautive. Les postes qui ne l'ont pas encore
telechargee ne la verront plus. Ceux qui l'ont deja installee doivent recevoir
une version **superieure** corrigeant le probleme : republier un ancien numero
ne fait pas redescendre les postes, c'est voulu.

## Ce qui protege les postes

- L'installateur n'est jamais execute sans que son empreinte SHA-256
  corresponde a celle declaree dans l'administration. La verification a lieu
  deux fois : apres le telechargement, puis **juste avant le lancement** —
  c'est la que le fichier devient du code execute.
- Le telechargement n'accepte que des adresses `https`.
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
