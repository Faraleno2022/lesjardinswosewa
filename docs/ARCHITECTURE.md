# Architecture Technique - MySchoolGN

## Vue d'ensemble

MySchoolGN est une application web Django suivant le pattern **MVT** (Model-View-Template). Elle est concue pour fonctionner a la fois en mode web et en mode desktop hors-ligne.

---

## Diagramme d'architecture

```
+----------------------------------------------------------+
|                    NAVIGATEUR / CLIENT                    |
|              Bootstrap 5 + JavaScript + HTML              |
+---------------------------+------------------------------+
                            |  HTTP/HTTPS
+---------------------------v------------------------------+
|                    DJANGO APPLICATION                     |
|                                                          |
|  +----------------+  +----------------+                  |
|  |   Middleware   |  |   URL Router   |                  |
|  | - LicenceCheck |  | ecole_moderne/ |                  |
|  | - CSRF         |  |    urls.py     |                  |
|  | - Session      |  +----------------+                  |
|  | - GZip         |                                      |
|  | - ImageCache   |                                      |
|  +----------------+                                      |
|                                                          |
|  +---------+ +---------+ +---------+ +---------+         |
|  | eleves  | |  notes  | |paiement | |depenses |         |
|  |  views  | |  views  | |  views  | |  views  |         |
|  +---------+ +---------+ +---------+ +---------+         |
|  +---------+ +---------+ +---------+ +---------+         |
|  |salaires | |  admin  | |utilisat.| | rapports|         |
|  |  views  | |  views  | |  views  | |  views  |         |
|  +---------+ +---------+ +---------+ +---------+         |
|                                                          |
|  +--------------------------------------------------+    |
|  |                    ORM Django                     |    |
|  |   Models: Eleve, Note, Paiement, Enseignant...   |    |
|  +--------------------------------------------------+    |
+---------------------------+------------------------------+
                            |
+---------------------------v------------------------------+
|                  BASE DE DONNEES MySQL                    |
+----------------------------------------------------------+

         +-------------------+  +--------------------+
         |  ReportLab /      |  |  OpenPyXL / Pandas |
         |  WeasyPrint       |  |  (Export Excel)    |
         |  (Generation PDF) |  +--------------------+
         +-------------------+
```

---

## Organisation des applications Django

### Applications personnalisees (Custom Apps)

| Application | Responsabilite principale |
|------------|--------------------------|
| `eleves` | Gestion des eleves, classes, ecoles, responsables |
| `notes` | Notes, evaluations, bulletins scolaires |
| `paiements` | Paiements de scolarite, echeanciers, recus |
| `depenses` | Depenses, fournisseurs, categories |
| `salaires` | Enseignants, pointage, calcul salaires |
| `abonnements` | Abonnements bus et cantine |
| `administration` | Configuration systeme, parametres ecole |
| `utilisateurs` | Authentification, roles, audit log |
| `rapports` | Generation de rapports et statistiques |
| `chatbot` | Assistant IA (OpenAI) |
| `comptes` | Module comptabilite |
| `bus` | Gestion transport scolaire |

### Applications Django integrees

- `django.contrib.admin` - Interface d'administration
- `django.contrib.auth` - Authentification
- `django.contrib.contenttypes` - Types de contenu
- `django.contrib.sessions` - Gestion des sessions
- `django.contrib.messages` - Messages flash
- `django.contrib.staticfiles` - Fichiers statiques
- `django.contrib.humanize` - Filtres d'affichage

---

## Modele de donnees principal

### Entites cles et leurs relations

```
Ecole
  |--- 1:N ---> Classe
  |--- 1:N ---> GrilleTarifaire
  |--- 1:N ---> Enseignant

Classe
  |--- 1:N ---> Eleve
  |--- 1:N ---> ClasseNote (notes)

Eleve
  |--- N:1 ---> Responsable (parent/tuteur)
  |--- 1:N ---> Paiement
  |--- 1:N ---> EcheancierPaiement
  |--- 1:N ---> HistoriqueEleve
  |--- 1:N ---> AbonnementBus
  |--- 1:N ---> AbonnementCantine

Profil (extension de User Django)
  |--- N:1 ---> User
  |--- 1:N ---> SessionUtilisateur
  |--- 1:N ---> JournalActivite

Depense
  |--- N:1 ---> CategorieDepense
  |--- N:1 ---> Fournisseur

Enseignant
  |--- N:1 ---> TypeEnseignant
  |--- N:1 ---> StatutEnseignant
```

---

## Middleware personnalise

### LicenceMiddleware
- Verifie la validite de la licence a chaque requete
- Bloque l'acces si la periode d'essai est expiree
- Redirige vers une page d'erreur de licence si invalide
- Exclut les URLs publiques (login, admin, etc.)

### ImageOptimizationMiddleware (dev uniquement)
- Met en cache les images optimisees
- Reduit la taille des images a la volee
- Active uniquement en mode DEBUG

---

## Securite

### Mesures implementees

| Mesure | Configuration |
|--------|--------------|
| CSRF | Active sur tous les formulaires POST |
| XSS | En-tete X-XSS-Protection |
| Clickjacking | X-Frame-Options: DENY |
| HTTPS (prod) | HSTS active, cookies securises |
| Content-Type | X-Content-Type-Options: nosniff |
| Referrer | Referrer-Policy configuree |

### Controle d'acces
- Decorateurs personnalises (`security_decorators.py`) pour verifier les roles
- Permissions granulaires par menu via `allowed_menus` (JSONField)
- Journalisation de toutes les actions utilisateur (CRUD, exports, impressions)
- Suivi des sessions avec adresse IP et User-Agent

### Mots de passe
- Hashage Django par defaut (PBKDF2)
- Validation de la complexite des mots de passe

---

## Generation de documents

### PDF (bulletins, cartes scolaires, recus)
- **ReportLab** : generation programmatique de PDF (tableaux, graphiques)
- **WeasyPrint** : rendu HTML/CSS vers PDF (bulletins stylises)
- Modeles de bulletin differencies par cycle :
  - Maternelle : appreciation par competence
  - Primaire : notes chiffrees + appreciation
  - Secondaire : notes + moyennes + rang + mention

### Excel (imports/exports)
- **OpenPyXL** : lecture et ecriture de fichiers `.xlsx`
- **Pandas** : manipulation et transformation des donnees tabulaires
- Import en masse des eleves depuis Excel
- Export des listes, paiements, statistiques

---

## Optimisation des performances

### QueryOptimizer
Module `utils/query_optimizer.py` qui :
- Detecte et previent les requetes N+1
- Pre-charge les relations via `select_related` et `prefetch_related`
- Met en cache les resultats frequents

### Cache Django
- Cache memoire pour les requetes repetitives
- Cache des images optimisees (middleware)
- Cache des listes d'eleves avec invalidation

---

## Configuration (settings.py)

### Variables d'environnement (.env)

| Variable | Valeur par defaut | Description |
|----------|------------------|-------------|
| `DJANGO_DEBUG` | `true` | Mode debug (False en production) |
| `DJANGO_SECRET_KEY` | (cle de dev) | Cle secrete Django |
| `TWILIO_ENABLED` | `false` | Activer les SMS Twilio |
| `DB_NAME` | - | Nom de la base de donnees |
| `DB_USER` | - | Utilisateur MySQL |
| `DB_PASSWORD` | - | Mot de passe MySQL |
| `DB_HOST` | `localhost` | Hote MySQL |
| `DB_PORT` | `3306` | Port MySQL |

### ALLOWED_HOSTS
- Developpement : `localhost`, `127.0.0.1`
- Production : `myschoolgn.space`, `*.pythonanywhere.com`

---

## Distribution desktop (PyInstaller)

### Processus de compilation

```bash
python build_exe.py
```

Ce script :
1. Collecte les fichiers statiques (`collectstatic`)
2. Lance PyInstaller avec `myschool.spec`
3. Inclut tous les DLLs necessaires (GTK, Pango, Cairo pour WeasyPrint)
4. Genere `dist/MySchoolGN/MySchoolGN.exe`

### Fichiers .spec disponibles
- `myschool.spec` - Application principale
- `LicenceTool_GS_Hadja.spec` - Gestionnaire de licences
- `generate_license.spec` - Generateur de licences
- `installer.spec` - Installeur Windows

### Systeme de licences offline
- `license_manager.py` : generation et validation des licences
- `generate_license_gui.py` : interface graphique pour les licences
- Licence stockee localement, validee a chaque demarrage
- Periode d'essai configurable
