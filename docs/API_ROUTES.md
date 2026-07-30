# Routes et vues - MySchoolGN

## Configuration principale des URLs

Fichier : `ecole_moderne/urls.py`

```
/                           -> Redirection vers login ou tableau de bord
/admin/                     -> Interface d'administration Django
/eleves/                    -> Module gestion des eleves
/notes/                     -> Module gestion des notes
/paiements/                 -> Module gestion des paiements
/depenses/                  -> Module gestion des depenses
/salaires/                  -> Module gestion des salaires
/abonnements/               -> Module abonnements bus/cantine
/administration/            -> Module administration
/utilisateurs/              -> Module gestion des utilisateurs
/rapports/                  -> Module rapports
/bus/                       -> Module transport scolaire
/chatbot/                   -> Module chatbot IA
```

---

## Module Eleves (`/eleves/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/eleves/` | `liste_eleves` | Liste paginee de tous les eleves |
| GET | `/eleves/liste/` | `liste_eleves` | Vue liste avec filtres |
| GET/POST | `/eleves/ajouter/` | `ajouter_eleve` | Formulaire d'inscription |
| GET | `/eleves/<id>/` | `detail_eleve` | Fiche detail d'un eleve |
| GET/POST | `/eleves/<id>/modifier/` | `modifier_eleve` | Modification des infos eleve |
| POST | `/eleves/<id>/supprimer/` | `supprimer_eleve` | Suppression (avec confirmation) |
| GET | `/eleves/<id>/carte/` | `carte_scolaire_pdf` | Generer la carte scolaire PDF |
| GET | `/eleves/export-excel/` | `export_eleves_excel` | Export liste Excel |
| POST | `/eleves/import-excel/` | `import_eleves_excel` | Import depuis Excel |
| GET | `/eleves/archives/` | `eleves_archives` | Eleves archives |
| POST | `/eleves/<id>/archiver/` | `archiver_eleve` | Archiver un eleve |
| GET/POST | `/eleves/classes/` | `liste_classes` | Gestion des classes |
| GET/POST | `/eleves/classes/ajouter/` | `ajouter_classe` | Ajouter une classe |
| GET/POST | `/eleves/ecoles/` | `liste_ecoles` | Gestion des ecoles |
| GET/POST | `/eleves/responsables/` | `liste_responsables` | Gestion des responsables |
| GET/POST | `/eleves/grille-tarifaire/` | `grille_tarifaire` | Tarifs par ecole/classe |

---

## Module Notes (`/notes/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/notes/` | `tableau_bord_notes` | Tableau de bord notes |
| GET | `/notes/classes/` | `liste_classes_notes` | Classes du systeme de notes |
| GET/POST | `/notes/saisie/<classe_id>/<matiere_id>/` | `saisir_notes` | Saisie des notes |
| GET | `/notes/bulletin/<eleve_id>/<periode>/` | `generer_bulletin` | Bulletin PDF |
| GET | `/notes/bulletin/<eleve_id>/<periode>/apercu/` | `apercu_bulletin` | Apercu HTML |
| POST | `/notes/bulletins/lot/<classe_id>/` | `bulletins_lot_pdf` | Tous les bulletins d'une classe |
| GET | `/notes/matieres/` | `liste_matieres` | Gestion des matieres |
| GET/POST | `/notes/matieres/ajouter/` | `ajouter_matiere` | Ajouter une matiere |
| GET | `/notes/statistiques/<classe_id>/` | `statistiques_classe` | Stats de la classe |
| GET | `/notes/releve/<eleve_id>/` | `releve_notes` | Releve de notes complet |
| GET/POST | `/notes/evaluations/` | `liste_evaluations` | Liste des evaluations |
| POST | `/notes/evaluations/ajouter/` | `ajouter_evaluation` | Creer une evaluation |

---

## Module Paiements (`/paiements/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/paiements/` | `tableau_bord_paiements` | Tableau de bord financier |
| GET | `/paiements/liste/` | `liste_paiements` | Liste tous les paiements |
| GET/POST | `/paiements/ajouter/` | `ajouter_paiement` | Enregistrer un paiement |
| GET | `/paiements/<id>/recu/` | `recu_pdf` | Recu de paiement PDF |
| GET | `/paiements/eleve/<eleve_id>/` | `paiements_eleve` | Historique paiements eleve |
| GET | `/paiements/en-retard/` | `paiements_en_retard` | Eleves en retard |
| GET | `/paiements/export-excel/` | `export_paiements_excel` | Export Excel |
| GET/POST | `/paiements/echeanciers/` | `gestion_echeanciers` | Echeanciers de paiement |
| GET/POST | `/paiements/types/` | `types_paiement` | Types de paiement |
| GET/POST | `/paiements/modes/` | `modes_paiement` | Modes de paiement |
| GET | `/paiements/statistiques/` | `statistiques_paiements` | Statistiques financieres |

---

## Module Depenses (`/depenses/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/depenses/` | `liste_depenses` | Liste des depenses |
| GET/POST | `/depenses/ajouter/` | `ajouter_depense` | Enregistrer une depense |
| GET | `/depenses/<id>/` | `detail_depense` | Detail d'une depense |
| POST | `/depenses/<id>/approuver/` | `approuver_depense` | Approuver la depense |
| POST | `/depenses/<id>/rejeter/` | `rejeter_depense` | Rejeter la depense |
| GET | `/depenses/export-excel/` | `export_depenses_excel` | Export Excel |
| GET/POST | `/depenses/categories/` | `categories_depense` | Categories |
| GET/POST | `/depenses/fournisseurs/` | `liste_fournisseurs` | Gestion fournisseurs |
| GET/POST | `/depenses/fournisseurs/ajouter/` | `ajouter_fournisseur` | Nouveau fournisseur |

---

## Module Salaires (`/salaires/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/salaires/` | `liste_enseignants` | Liste des enseignants |
| GET/POST | `/salaires/ajouter/` | `ajouter_enseignant` | Nouvelle fiche enseignant |
| GET | `/salaires/<id>/` | `detail_enseignant` | Fiche enseignant |
| GET/POST | `/salaires/<id>/modifier/` | `modifier_enseignant` | Modifier infos |
| GET/POST | `/salaires/pointage/` | `saisir_pointage` | Saisie des presences |
| GET | `/salaires/<id>/bulletin/` | `bulletin_salaire_pdf` | Bulletin salaire PDF |
| GET | `/salaires/rapport-mensuel/` | `rapport_salaires` | Rapport mensuel |
| GET | `/salaires/export-excel/` | `export_salaires_excel` | Export Excel |

---

## Module Abonnements (`/abonnements/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/abonnements/` | `liste_abonnements` | Vue d'ensemble |
| GET | `/abonnements/bus/` | `abonnements_bus` | Liste abonnements bus |
| GET/POST | `/abonnements/bus/ajouter/` | `ajouter_abonnement_bus` | Inscrire au bus |
| GET | `/abonnements/cantine/` | `abonnements_cantine` | Liste abonnements cantine |
| GET/POST | `/abonnements/cantine/ajouter/` | `ajouter_abonnement_cantine` | Inscrire a la cantine |
| POST | `/abonnements/<id>/resilier/` | `resilier_abonnement` | Resilier un abonnement |

---

## Module Administration (`/administration/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/administration/` | `tableau_bord_admin` | Tableau de bord general |
| GET/POST | `/administration/ecole/` | `config_ecole` | Parametres de l'ecole |
| GET/POST | `/administration/annee-scolaire/` | `config_annee` | Annee scolaire en cours |
| GET | `/administration/statistiques/` | `statistiques_globales` | Stats globales |
| GET | `/administration/sauvegarde/` | `sauvegarde_bdd` | Export/sauvegarde BDD |

---

## Module Utilisateurs (`/utilisateurs/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET/POST | `/utilisateurs/login/` | `connexion` | Page de connexion |
| GET | `/utilisateurs/logout/` | `deconnexion` | Deconnexion |
| GET | `/utilisateurs/` | `liste_utilisateurs` | Gestion des comptes |
| GET/POST | `/utilisateurs/ajouter/` | `ajouter_utilisateur` | Creer un compte |
| GET/POST | `/utilisateurs/<id>/modifier/` | `modifier_utilisateur` | Modifier le compte |
| POST | `/utilisateurs/<id>/desactiver/` | `desactiver_utilisateur` | Desactiver un compte |
| GET/POST | `/utilisateurs/profil/` | `mon_profil` | Mon profil |
| GET/POST | `/utilisateurs/changer-mdp/` | `changer_mot_de_passe` | Changer mon mot de passe |
| GET | `/utilisateurs/journal/` | `journal_activite` | Log d'activite (admin) |
| GET | `/utilisateurs/sessions/` | `sessions_actives` | Sessions en cours |

---

## Module Rapports (`/rapports/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/rapports/` | `liste_rapports` | Menu des rapports |
| GET | `/rapports/financier/` | `rapport_financier` | Rapport recettes/depenses |
| GET | `/rapports/effectifs/` | `rapport_effectifs` | Rapport des effectifs |
| GET | `/rapports/paiements/` | `rapport_paiements` | Etat des paiements |
| GET | `/rapports/pedagogique/` | `rapport_pedagogique` | Resultats scolaires |
| GET | `/rapports/salaires/` | `rapport_salaires` | Masse salariale |
| GET | `/rapports/financier/pdf/` | `rapport_financier_pdf` | Rapport financier PDF |
| GET | `/rapports/financier/excel/` | `rapport_financier_excel` | Rapport financier Excel |

---

## Module Chatbot (`/chatbot/`)

| Methode | URL | Vue | Description |
|---------|-----|-----|-------------|
| GET | `/chatbot/` | `interface_chatbot` | Interface du chatbot |
| POST | `/chatbot/message/` | `envoyer_message` | Envoyer un message (AJAX) |
| POST | `/chatbot/reinitialiser/` | `reinitialiser_conversation` | Nouvelle conversation |

---

## Conventions de reponse

### Vues HTML standard
- Retournent un template HTML rendu
- Utilisent `render(request, 'template.html', contexte)`
- Les erreurs sont affichees via `messages.error()`

### Vues AJAX (JSON)
- Content-Type: `application/json`
- Reponse succes : `{"status": "ok", "data": {...}}`
- Reponse erreur : `{"status": "error", "message": "..."}`

### Vues de telechargement (PDF/Excel)
- Content-Type: `application/pdf` ou `application/vnd.openxmlformats...`
- Header: `Content-Disposition: attachment; filename="nom_fichier.pdf"`

---

## Protection des vues

Toutes les vues (sauf login) sont protegees par :

1. `@login_required` - L'utilisateur doit etre connecte
2. `@role_requis(...)` - L'utilisateur doit avoir le role requis
3. Verification CSRF sur tous les formulaires POST

Exemple de vue protegee :
```python
@login_required
@role_requis('Administrateur', 'Directeur', 'Comptable')
def liste_paiements(request):
    ...
```
