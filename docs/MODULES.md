# Description des modules - MySchoolGN

## Module 1 : Eleves (`eleves/`)

### Role
Coeur du systeme. Gere l'ensemble du cycle de vie d'un eleve : inscription, suivi en cours d'annee, archivage en fin d'annee scolaire.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `Ecole` | Etablissement scolaire (nom, adresse, logo, prefixe matricule) |
| `Classe` | Classe ou niveau (Garderie, PS, MS, GS, CP, CE1..., Terminale) |
| `Eleve` | Eleve avec infos personnelles, matricule, photo, classe, statut |
| `Responsable` | Parent ou tuteur (nom, telephone, adresse, profession) |
| `HistoriqueEleve` | Suivi des changements de classe/statut (passage, redoublement, sortie) |
| `GrilleTarifaire` | Tarifs de scolarite par ecole et classe (inscription, mensualite, etc.) |

### Fonctionnalites cles

- **Inscription** : Formulaire complet avec generation automatique du matricule
  - Format : `[PREFIXE_ECOLE][ANNEE][SEQUENCE]` (ex: `GS2024001`)
- **Liste des eleves** : Vue optimisee avec recherche, filtres par classe/statut
- **Fiche eleve** : Detail complet, photo, responsable, historique paiements
- **Carte scolaire** : Generation PDF de la carte officielle de l'eleve
- **Import Excel** : Inscription en masse depuis un fichier `.xlsx`
- **Export Excel** : Export de la liste des eleves avec toutes les informations
- **Archivage** : Transfert des eleves en fin d'annee scolaire avec conservation des donnees

### Fichiers cles
```
eleves/
  models.py          # Modeles Ecole, Classe, Eleve, Responsable...
  views.py           # Vues principales (172 000+ lignes)
  forms.py           # Formulaires de saisie
  urls.py            # Routes du module
  utils.py           # Utilitaires (generation matricule, etc.)
  pdf_utils.py       # Generation des cartes scolaires PDF
```

---

## Module 2 : Notes (`notes/`)

### Role
Gestion complete de l'evaluation scolaire : saisie des notes, calcul des moyennes, generation des bulletins par cycle pedagogique.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `ClasseNote` | Classe rattachee au systeme de notes |
| `MatiereNote` | Matiere avec coefficient et enseignant responsable |
| `Evaluation` | Evaluation individuelle (type, periode, date, notes des eleves) |

### Types d'evaluations
- **Devoir** : Controle continu (coefficient reduit)
- **Composition** : Evaluation trimestrielle (coefficient plein)
- **Examen** : Examen de passage (coefficient fort)

### Periodes
- Mensuelle (mois de septembre a juin)
- Trimestrielle (T1, T2, T3)

### Bulletins par cycle

| Cycle | Specificites |
|-------|-------------|
| **Maternelle** | Appreciation par competence (Acquis / En cours / Non acquis), pas de notes chiffrees |
| **Primaire** | Notes sur 10 ou 20, moyennes, appreciation, rang de classe |
| **Secondaire** | Notes sur 20, moyennes, coefficients, rang, mention, signature |

### Fonctionnalites cles

- Saisie de notes en grille (tous les eleves d'une classe pour une matiere)
- Calcul automatique des moyennes generales et par matiere
- Classement des eleves dans la classe
- Attribution des mentions (Excellent, Tres Bien, Bien, Assez Bien, Passable, Insuffisant)
- Impression des bulletins individuels ou en lot (toute la classe)
- Analyse statistique de la classe (moyenne de classe, taux de reussite)
- Gestion de l'analyse speciale Maternelle Intelligente (voir `SYSTEME_ANALYSE_MATERNELLE_INTELLIGENTE.md`)

### Fichiers cles
```
notes/
  models.py          # Modeles ClasseNote, MatiereNote, Evaluation
  views.py           # Vues (26 000+ lignes)
  forms.py           # Formulaires de saisie
  urls.py            # Routes
  pdf_bulletins.py   # Generation des bulletins PDF
```

---

## Module 3 : Paiements (`paiements/`)

### Role
Suivi financier des scolarites : enregistrement des paiements, gestion des echeances, edition des recus.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `Paiement` | Paiement effectue (montant, date, mode, statut, numero de recu) |
| `TypePaiement` | Type de paiement (Inscription, Scolarite mensuelle, Frais divers...) |
| `ModePaiement` | Mode de reglement (Especes, Virement, Cheque, Mobile Money) |
| `EcheancierPaiement` | Calendrier des paiements dus par eleve |

### Numerotation des recus
Format automatique : `REC[ANNEE][SEQUENCE5CHIFFRES]`
- Exemple : `REC202400001`

### Paiement partiel intelligent
Le systeme alloue intelligemment les paiements partiels :
1. Priorite aux paiements les plus anciens en retard
2. Allocation automatique sur plusieurs echeances
3. Calcul du solde restant du
4. Voir `docs/GUIDE_PAIEMENT_PARTIEL_INTELLIGENT.md` pour le detail

### Fonctionnalites cles

- Saisie d'un paiement avec selection de l'eleve et du type
- Generation instantanee du recu PDF
- Tableau de bord des paiements en attente / en retard
- Historique complet par eleve
- Export des paiements en Excel (avec filtres date, classe, type)
- Statistiques financieres par periode et par classe
- Gestion des grilles tarifaires (tarifs differencies par ecole et classe)

### Fichiers cles
```
paiements/
  models.py          # Modeles Paiement, TypePaiement, EcheancierPaiement
  views.py           # Vues (7 800+ lignes)
  forms.py           # Formulaires
  urls.py            # Routes
  pdf_recus.py       # Generation recus PDF
```

---

## Module 4 : Depenses (`depenses/`)

### Role
Gestion des sorties d'argent de l'etablissement : suivi des depenses, validation par workflow, gestion des fournisseurs.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `Depense` | Depense avec montant, categorie, fournisseur, statut de validation |
| `CategorieDepense` | Categories (Fournitures, Entretien, Salaires, Electricite...) |
| `Fournisseur` | Fournisseur avec coordonnees, NIF et RCCM fiscaux |

### Workflow de validation

```
Saisie (en_attente)
      |
      v
Verification comptable
      |
   +--+--+
   |     |
   v     v
Approuvee  Rejetee
```

### Fonctionnalites cles

- Enregistrement des depenses avec pieces justificatives (photo)
- Validation a deux niveaux (comptable + directeur)
- Tableau de bord des depenses par categorie et par periode
- Export Excel des depenses
- Gestion complete du fichier fournisseurs

### Fichiers cles
```
depenses/
  models.py          # Modeles Depense, CategorieDepense, Fournisseur
  views.py           # Vues (2 800+ lignes)
  forms.py           # Formulaires
  urls.py            # Routes
```

---

## Module 5 : Salaires (`salaires/`)

### Role
Gestion des ressources humaines enseignantes : fiches enseignants, pointage des presences, calcul et edition des bulletins de salaire.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `Enseignant` | Fiche enseignant (nom, specialite, type de contrat, taux) |
| `TypeEnseignant` | Type (Garderie, Maternelle, Primaire, Secondaire) |
| `StatutEnseignant` | Statut (Actif, En conge, Suspendu, Quitte) |
| `Pointage` | Presence journaliere ou mensuelle |

### Modes de remuneration

| Type | Description |
|------|-------------|
| **Taux horaire** | Remuneration calculee sur le nombre d'heures effectuees |
| **Forfait mensuel** | Salaire fixe independamment des heures |

### Fonctionnalites cles

- Fiche complete de chaque enseignant
- Pointage mensuel (presences, absences, retards)
- Calcul automatique du salaire en fonction du pointage
- Edition du bulletin de salaire PDF
- Historique des salaires verses
- Rapport de la masse salariale par periode

### Fichiers cles
```
salaires/
  models.py          # Modeles Enseignant, Pointage
  views.py           # Vues (3 500+ lignes)
  forms.py           # Formulaires
  urls.py            # Routes
  README_POINTAGE.md # Documentation specifique du pointage
```

---

## Module 6 : Abonnements (`abonnements/`)

### Role
Gestion des services parascolaires : transport scolaire (bus) et restauration (cantine).

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `AbonnementBus` | Abonnement transport avec zone et itineraire |
| `AbonnementCantine` | Abonnement restauration avec type de repas |

### Types de repas (cantine)

| Type | Description |
|------|-------------|
| Dejeuner | Repas de midi uniquement |
| Gouter | Collation de l'apres-midi |
| Complet | Dejeuner + Gouter |

### Fonctionnalites cles

- Inscription et resiliation des abonnements
- Facturation mensuelle des abonnements
- Liste des abonnes par service
- Suivi des paiements d'abonnements
- Statistiques d'utilisation (nombre d'abonnes par route, par service)

---

## Module 7 : Administration (`administration/`)

### Role
Configuration du systeme et gestion des parametres globaux de l'etablissement.

### Fonctionnalites

- Configuration des informations de l'ecole (nom, logo, devise, contacts)
- Parametres systeme (annee scolaire en cours, periodes d'evaluation)
- Gestion des cycles scolaires et niveaux
- Tableau de bord administrateur (vue d'ensemble de toutes les statistiques)
- Configuration des modeles de documents (entete bulletins, etc.)

### Fichiers cles
```
administration/
  views.py           # Vues (958+ lignes)
  urls.py            # Routes
```

---

## Module 8 : Utilisateurs (`utilisateurs/`)

### Role
Gestion des comptes utilisateurs, des roles et des permissions, ainsi que l'audit de toutes les actions.

### Modeles principaux

| Modele | Description |
|--------|-------------|
| `Profil` | Extension du User Django avec role et permissions specifiques |
| `SessionUtilisateur` | Suivi des connexions (IP, User-Agent, duree) |
| `JournalActivite` | Log de toutes les actions (CRUD, exports, impressions) |
| `ParametreSysteme` | Paires cle-valeur de configuration systeme |

### Roles disponibles
Voir [ROLES_PERMISSIONS.md](ROLES_PERMISSIONS.md) pour le detail complet.

### Audit log
Chaque action enregistre :
- Utilisateur
- Type d'action (CREATE, UPDATE, DELETE, EXPORT, PRINT, LOGIN, LOGOUT)
- Module concerne
- Objet affecte
- Horodatage
- Adresse IP

### Fonctionnalites

- Creation et gestion des comptes utilisateurs
- Attribution des roles et permissions par menu
- Consultation du journal d'activite (avec filtres)
- Gestion des sessions actives
- Reinitialisation des mots de passe
- Tableau de bord de securite

---

## Module 9 : Rapports (`rapports/`)

### Role
Generation de rapports statistiques et de synthese pour la direction et la comptabilite.

### Types de rapports

| Rapport | Description |
|---------|-------------|
| Rapport financier | Recettes, depenses, solde par periode |
| Rapport pedagogique | Resultats par classe, taux de reussite |
| Rapport des effectifs | Nombre d'eleves par classe, evolution |
| Rapport de paiements | Etat des paiements, retards, taux de recouvrement |
| Rapport de salaires | Masse salariale, cout par departement |

### Formats d'export
- PDF (mise en page professionnelle avec entete ecole)
- Excel (.xlsx) pour retraitement
- Affichage web interactif avec graphiques

---

## Module 10 : Chatbot (`chatbot/`)

### Role
Assistant intelligent integre pour aider les utilisateurs a naviguer dans le systeme et repondre a leurs questions.

### Integration
- Utilise l'API OpenAI (GPT)
- Contexte de l'ecole injecte dans les prompts
- Historique de conversation en session
- Reponses en francais

### Cas d'usage
- Aide a la navigation dans le systeme
- Explication des fonctionnalites
- Statistiques rapides sur demande
- Support utilisateur de premier niveau

### Fichiers cles
```
chatbot/
  views.py           # Vues de l'interface chatbot
  urls.py            # Routes
CHATBOT_REVISION_GUIDE.md  # Documentation detaillee
```

---

## Module 11 : Bus (`bus/`)

### Role
Gestion operationnelle du transport scolaire (complement du module abonnements).

### Fonctionnalites
- Definition des routes et zones de ramassage
- Affectation des eleves aux bus/routes
- Suivi des presences dans les bus
- Gestion des conducteurs et vehicules

---

## Utilitaires transversaux

### `utils/query_optimizer.py`
Optimisation automatique des requetes ORM pour prevenir les problemes de performance N+1.

### `security_decorators.py`
Decorateurs Python pour la verification des roles sur chaque vue :
```python
@role_requis('Administrateur', 'Directeur')
def ma_vue(request):
    ...
```

### `pdf_utils.py`
Fonctions utilitaires communes pour la generation de PDF :
- En-tete avec logo de l'ecole
- Pied de page avec numerotation
- Styles communs (polices, couleurs)

### `scripts/`
Scripts utilitaires pour la maintenance et la migration :
- `create_maternelle_data.py` : Creation de donnees d'exemple Maternelle
- `creer_appreciations_*.py` : Initialisation des grilles d'appreciation
- `diagnostic_classes.py` : Diagnostic de la coherence des donnees
