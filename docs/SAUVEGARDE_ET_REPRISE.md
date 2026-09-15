# Sauvegarde et reprise après panne — version installable

Ce document couvre le scénario le plus courant et le plus coûteux : **la machine
de l'école tombe en panne**. Disque mort, vol, foudre, ordinateur noyé.

Deux mécanismes indépendants protègent l'installation. Ils ne se remplacent pas.

| | Sauvegarde locale (ce document) | Synchronisation en ligne ([SYNCHRONISATION_OFFLINE.md](SYNCHRONISATION_OFFLINE.md)) |
|---|---|---|
| Protège contre | la perte des données | l'interruption de l'activité |
| Fonctionne sans Internet | oui | non |
| Contient les photos et pièces jointes | oui | non (l'instantané initial exclut les fichiers) |
| Contient les comptes utilisateurs | oui | non |
| Copie hors des murs de l'école | oui, via le dossier cloud | oui, en continu |

## Ce qui se passe sans rien configurer

Dès l'installation, aucune action n'est requise :

- **Toutes les 6 heures**, pendant que MySchoolGN tourne, une archive est créée
  et déposée sur **chaque destination détectée** (règle 3-2-1) :
  1. le dossier `sauvegardes\` de l'installation ;
  2. le dossier cloud synchronisé du poste, s'il existe — OneDrive, Google Drive
     (« Mon Drive »), Dropbox, iCloud Drive → sous-dossier
     « Sauvegardes MySchoolGN » ;
  3. **toute clé USB ou disque externe branché** au moment de la sauvegarde.
- Chaque archive (~10 Mo) contient la base de données, tout le dossier `media\`
  (photos d'élèves, logos, pièces justificatives) et un manifeste décrivant son
  contenu avec un condensat de contrôle.
- **Rotation** par destination : 7 quotidiennes, 4 hebdomadaires,
  12 mensuelles. Une corruption découverte trois semaines plus tard reste donc
  récupérable.
- Chaque exécution est tracée dans `logs\sauvegarde.log`.

Deux garanties techniques importantes :

- La base n'est jamais copiée comme un fichier ordinaire. Elle passe par l'API
  de sauvegarde en ligne de SQLite, donc **la copie est cohérente même si la
  secrétaire saisit un paiement au même instant**. Une copie « à chaud » à coups
  de `copier/coller` produit, elle, une archive corrompue une fois sur dix —
  qu'on ne découvre que le jour de la restauration.
- La sauvegarde fonctionne **même licence expirée**, et sans ouvrir
  l'application.

## À faire une fois par poste (recommandé)

1. **Brancher un support et le laisser sur place** : une clé USB dédiée, ou un
   petit disque externe. C'est la copie qui sauve quand Internet est absent.
2. **Installer la sauvegarde nocturne** : clic droit sur
   `Planifier_Sauvegarde.bat` → *Exécuter en tant qu'administrateur*. Elle
   sauvegarde chaque nuit à 20h00, **même application fermée**.
3. **Vérifier que le dossier cloud se synchronise** réellement (icône OneDrive /
   Google Drive verte, pas en pause).

## Commandes

Sur un poste installé (exécutable) :

```bash
MySchoolGN.exe --sauvegarder
```

```bash
MySchoolGN.exe --lister-sauvegardes
```

Sauvegarde immédiate sans ligne de commande : double-clic sur
`Sauvegarder_MySchoolGN.bat`.

Sur un poste de développement ou sur le serveur :

```bash
python manage.py sauvegarder
```

```bash
python manage.py sauvegarder --lister
```

```bash
python manage.py sauvegarder --destination "E:\Sauvegardes" --destination "D:\Copie"
```

## Réglages facultatifs

Copier `sauvegarde_config.example.json` en `sauvegarde_config.json`, à côté de
`MySchoolGN.exe`, puis redémarrer l'application. Permet de fixer les
destinations à la main, de changer l'intervalle, de chiffrer les archives ou de
désactiver la sauvegarde automatique.

Le chiffrement AES exige le module `pyzipper`. S'il est absent, l'archive est
écrite **en clair** et un avertissement est journalisé : elle contient des
données personnelles d'élèves, donc protégez le support (BitLocker sur la clé,
dossier cloud du compte de l'école et non d'un compte personnel).

## Procédure de reprise après panne

Objectif réaliste : rouvrir le secrétariat en **30 à 45 minutes**, avec au pire
une demi-journée de saisie à reprendre.

1. **Récupérer la dernière archive.** Sur la clé USB, ou en se connectant au
   compte cloud depuis n'importe quel ordinateur. Vérifier la date du fichier.
2. **Installer MySchoolGN** sur la nouvelle machine.
3. **Activer la licence.** Elle est liée au matériel : une machine neuve exige
   un nouveau fichier `.lic`, sinon toutes les pages répondent « accès refusé ».
   *À préparer d'avance* : garder une licence distribuable en réserve, ou le
   contact de l'éditeur dans le classeur de l'école. C'est le vrai goulot de la
   reprise, pas les données.
4. **Restaurer :**

   ```bash
   MySchoolGN.exe --restaurer "E:\Sauvegardes MySchoolGN\myschoolgn_sauvegarde_20260812_200000.zip"
   ```

   Sans `--confirmer`, la commande **n'écrit rien** : elle affiche seulement la
   date, la machine d'origine et les compteurs (élèves, paiements) de l'archive.
   Vérifier que c'est la bonne, puis relancer avec `--confirmer`.

   La base et les médias déjà présents sont mis de côté sous un nom horodaté,
   jamais supprimés. Une archive tronquée est refusée **avant** que l'existant
   ne soit touché.
5. **Redémarrer MySchoolGN** et contrôler : nombre d'élèves, derniers paiements,
   photos visibles.
6. **Si la synchronisation est active**, la lancer pour récupérer ce que les
   autres postes ont enregistré depuis la dernière archive.

## Le geste qui fait la différence

**Une restauration de test par mois**, sur un autre ordinateur ou dans un
dossier séparé. Une sauvegarde jamais restaurée n'est pas une sauvegarde. C'est
à ce moment-là qu'on découvre le zip tronqué, la clé jamais branchée ou le cloud
en pause — pas le jour de la panne.

Contrôle mensuel, trois minutes :

```bash
MySchoolGN.exe --lister-sauvegardes
```

Vérifier que la plus récente date de moins de 24 h et qu'elle est présente sur
**au moins deux** destinations.
