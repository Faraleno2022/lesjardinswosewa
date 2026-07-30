# MySchoolGN - Systeme de Gestion Scolaire

**MySchoolGN** est un systeme de gestion scolaire complet developpe avec Django (Python), destine aux etablissements scolaires en Guinee. Il couvre l'ensemble des besoins administratifs, pedagogiques et financiers d'une ecole, du cycle maternelle au lycee.

---

## Table des matieres

1. [Apercu du systeme](#apercu)
2. [Fonctionnalites principales](#fonctionnalites)
3. [Stack technique](#stack)
4. [Installation](#installation)
5. [Structure du projet](#structure)
6. [Modules](#modules)
7. [Roles et permissions](#roles)
8. [Deploiement](#deploiement)
9. [Documentation complementaire](#docs)

---

## Apercu du systeme <a name="apercu"></a>

MySchoolGN est deploye en deux modes :

| Mode | Description |
|------|-------------|
| **Application web** | Accessible via navigateur sur `myschoolgn.space` ou `gshadjakanfingdiane.pythonanywhere.com` |
| **Application desktop** | Executable `.exe` standalone pour usage hors-ligne (Windows), avec systeme de licence |

Le systeme supporte plusieurs etablissements (multi-ecoles), gere les cycles maternelle, primaire et secondaire, et produit tous les documents officiels (bulletins, cartes scolaires, recus de paiement).

---

## Fonctionnalites principales <a name="fonctionnalites"></a>

### Gestion des eleves
- Inscription et suivi des eleves (matricule auto-genere)
- Gestion des responsables/parents
- Import/export Excel des listes d'eleves
- Carte scolaire PDF
- Historique et archivage des eleves

### Gestion des notes
- Saisie des notes par matiere, trimestre et evaluation
- Bulletins scolaires PDF (Maternelle, Primaire, Secondaire)
- Calcul automatique des moyennes et rangs
- Analyse de performance par classe

### Gestion des paiements
- Saisie et suivi des paiements de scolarite
- Paiements partiels avec allocation intelligente
- Grilles tarifaires par ecole et classe
- Generation de recus numerotes automatiquement (format RECANNEExxxxx)
- Echeanciers de paiement

### Gestion des depenses
- Enregistrement des depenses par categorie
- Workflow de validation (en attente, approuvee, rejetee)
- Gestion des fournisseurs (avec NIF/RCCM)

### Gestion des salaires
- Fiches enseignants (taux horaire ou forfait)
- Pointage et suivi des presences
- Calcul des salaires mensuels

### Abonnements
- Abonnements transport scolaire (bus par zone/itineraire)
- Abonnements cantine (dejeuner, gouter, complet)

### Administration
- Configuration multi-ecoles
- Parametres systeme
- Journal d'activite (audit log complet)
- Rapports statistiques exportables

### Chatbot IA
- Assistant integre via l'API OpenAI pour aider les utilisateurs

---

## Stack technique <a name="stack"></a>

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.x + Django 5.2.6 |
| Base de donnees | MySQL / MariaDB |
| Frontend | Django Templates + Bootstrap 5 + JavaScript |
| Generation PDF | ReportLab 4.4.3 + WeasyPrint 63.1 |
| Export Excel | OpenPyXL 3.1.5 + Pandas |
| SMS | Twilio 9.8.1 (optionnel) |
| Chatbot | OpenAI API |
| Distribution desktop | PyInstaller |
| Traitement images | Pillow 11.3.0 |

---

## Installation <a name="installation"></a>

Voir [docs/INSTALLATION.md](docs/INSTALLATION.md) pour le guide complet.

**Demarrage rapide (developpement) :**

```bash
# 1. Cloner le depot
git clone <url-du-depot>
cd GS_hadja_kanfing_dian--main

# 2. Creer et activer l'environnement virtuel
python -m venv venv
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# 3. Installer les dependances
pip install -r requirements.txt

# 4. Configurer l'environnement
cp .env.example .env
# Editer .env avec vos parametres

# 5. Appliquer les migrations
python manage.py migrate

# 6. Creer un superutilisateur
python manage.py createsuperuser

# 7. Lancer le serveur
python manage.py runserver
```

---

## Structure du projet <a name="structure"></a>

```
GS_hadja_kanfing_dian--main/
|
|-- ecole_moderne/          # Configuration Django (settings, urls, wsgi)
|-- eleves/                 # Module gestion des eleves
|-- notes/                  # Module gestion des notes et bulletins
|-- paiements/              # Module gestion des paiements
|-- depenses/               # Module gestion des depenses
|-- salaires/               # Module gestion des enseignants et salaires
|-- abonnements/            # Module bus et cantine
|-- administration/         # Module administration et configuration
|-- utilisateurs/           # Module utilisateurs, roles et authentification
|-- rapports/               # Module rapports et statistiques
|-- chatbot/                # Module assistant IA
|-- comptes/                # Module comptabilite
|-- bus/                    # Gestion transport scolaire
|
|-- templates/              # Templates HTML (un sous-dossier par app)
|-- static/                 # Fichiers statiques (CSS, JS, images)
|-- media/                  # Fichiers uploades (photos eleves, logos)
|
|-- manage.py               # Point d'entree Django
|-- requirements.txt        # Dependances Python
|-- .env                    # Variables d'environnement (ne pas commiter)
|-- build_exe.py            # Script de compilation .exe
|-- license_manager.py      # Gestionnaire de licences offline
```

---

## Modules <a name="modules"></a>

Voir [docs/MODULES.md](docs/MODULES.md) pour la description detaillee de chaque module.

| Module | App Django | Description |
|--------|-----------|-------------|
| Eleves | `eleves` | Inscription, suivi, archivage des eleves |
| Notes | `notes` | Saisie notes, bulletins, statistiques |
| Paiements | `paiements` | Scolarite, recus, echeanciers |
| Depenses | `depenses` | Depenses, fournisseurs, validation |
| Salaires | `salaires` | Enseignants, pointage, paie |
| Abonnements | `abonnements` | Bus et cantine |
| Administration | `administration` | Config ecole, parametres |
| Utilisateurs | `utilisateurs` | Comptes, roles, audit |
| Rapports | `rapports` | Exports, statistiques |
| Chatbot | `chatbot` | Assistant IA |

---

## Roles et permissions <a name="roles"></a>

Voir [docs/ROLES_PERMISSIONS.md](docs/ROLES_PERMISSIONS.md) pour le detail des acces.

| Role | Description |
|------|-------------|
| Administrateur | Acces complet a tous les modules |
| Directeur | Acces lecture/ecriture sauf gestion utilisateurs avancee |
| Comptable | Acces paiements, depenses, salaires, rapports financiers |
| Secretaire | Gestion eleves, inscriptions, saisie paiements |
| Enseignant | Saisie notes pour ses classes uniquement |
| Surveillant | Consultation liste eleves, gestion abonnements |

---

## Deploiement <a name="deploiement"></a>

Voir [docs/INSTALLATION.md](docs/INSTALLATION.md) pour le guide de deploiement complet.

### Web (PythonAnywhere)
- Hote : `gshadjakanfingdiane.pythonanywhere.com`
- Domaine personnalise : `myschoolgn.space`
- Base de donnees : MySQL distant

### Desktop (Windows .exe)
```bash
# Compiler l'executable
python build_exe.py

# L'executable est genere dans dist/MySchoolGN/
```

Variables d'environnement requises en production :
```
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<cle-secrete-forte>
TWILIO_ENABLED=false
```

---

## Documentation complementaire <a name="docs"></a>

| Document | Description |
|----------|-------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture technique detaillee |
| [docs/INSTALLATION.md](docs/INSTALLATION.md) | Guide d'installation et deploiement |
| [docs/MODULES.md](docs/MODULES.md) | Description detaillee des modules |
| [docs/API_ROUTES.md](docs/API_ROUTES.md) | Liste des routes et vues |
| [docs/ROLES_PERMISSIONS.md](docs/ROLES_PERMISSIONS.md) | Systeme de roles et permissions |
| [docs/GUIDE_UTILISATEUR.md](docs/GUIDE_UTILISATEUR.md) | Manuel utilisateur |
| [docs/GUIDE_PAIEMENT_PARTIEL_INTELLIGENT.md](docs/GUIDE_PAIEMENT_PARTIEL_INTELLIGENT.md) | Systeme de paiement partiel |
| [CHATBOT_REVISION_GUIDE.md](CHATBOT_REVISION_GUIDE.md) | Documentation du chatbot |

---

## Licence

Ce logiciel est protege par un systeme de licence. Chaque installation necessite une cle de licence valide generee via `license_manager.py` ou l'outil `generate_license_gui.py`.

Pour toute information, contacter l'equipe de developpement.
