# Roles et Permissions - MySchoolGN

## Vue d'ensemble du systeme de controle d'acces

MySchoolGN utilise un systeme de **Role-Based Access Control (RBAC)** avec 6 roles predefinies. Les permissions sont granulaires par module et par action (lecture, ecriture, suppression, export, impression).

---

## Les 6 roles du systeme

### 1. Administrateur

**Description** : Acces complet a l'ensemble du systeme. Peut creer et gerer les autres comptes utilisateurs.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | OK | OK | OK | OK | OK |
| Notes | OK | OK | OK | OK | OK |
| Paiements | OK | OK | OK | OK | OK |
| Depenses | OK | OK | OK | OK | OK |
| Salaires | OK | OK | OK | OK | OK |
| Abonnements | OK | OK | OK | OK | OK |
| Administration | OK | OK | OK | OK | OK |
| Utilisateurs | OK | OK | OK | OK | OK |
| Rapports | OK | - | - | OK | OK |
| Journal activite | OK | - | - | OK | - |

---

### 2. Directeur

**Description** : Acces lecture/ecriture sur tous les modules operationnels. Ne peut pas gerer les comptes utilisateurs ni les parametres systeme avances.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | OK | OK | - | OK | OK |
| Notes | OK | OK | - | OK | OK |
| Paiements | OK | OK | - | OK | OK |
| Depenses | OK | OK (validation) | - | OK | OK |
| Salaires | OK | OK | - | OK | OK |
| Abonnements | OK | OK | - | OK | OK |
| Administration | OK | Partiel | - | - | - |
| Utilisateurs | Consultation | - | - | - | - |
| Rapports | OK | - | - | OK | OK |
| Journal activite | OK | - | - | OK | - |

---

### 3. Comptable

**Description** : Specialise dans la gestion financiere. Acces complet aux paiements, depenses et salaires. Lecture seule sur les eleves.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | OK | - | - | OK | - |
| Notes | - | - | - | - | - |
| Paiements | OK | OK | - | OK | OK |
| Depenses | OK | OK | - | OK | OK |
| Salaires | OK | OK | - | OK | OK |
| Abonnements | OK | OK | - | OK | - |
| Administration | - | - | - | - | - |
| Utilisateurs | - | - | - | - | - |
| Rapports financiers | OK | - | - | OK | OK |
| Journal activite | Partiel (ses actions) | - | - | - | - |

---

### 4. Secretaire

**Description** : Gestion du quotidien scolaire. Inscription des eleves, saisie des paiements. Pas d'acces aux rapports financiers detailles.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | OK | OK | - | OK | OK |
| Notes | Lecture | - | - | - | OK |
| Paiements | OK | OK | - | - | OK |
| Depenses | - | - | - | - | - |
| Salaires | - | - | - | - | - |
| Abonnements | OK | OK | - | - | - |
| Administration | - | - | - | - | - |
| Utilisateurs | - | - | - | - | - |
| Rapports | Effectifs uniquement | - | - | - | OK |
| Journal activite | - | - | - | - | - |

---

### 5. Enseignant

**Description** : Acces limite a son propre domaine d'enseignement. Ne peut saisir des notes que pour ses propres classes et matieres.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | Lecture (ses classes) | - | - | - | - |
| Notes | OK (ses classes) | OK (ses classes) | - | - | OK |
| Paiements | - | - | - | - | - |
| Depenses | - | - | - | - | - |
| Salaires | Son bulletin uniquement | - | - | - | OK |
| Abonnements | - | - | - | - | - |
| Administration | - | - | - | - | - |
| Utilisateurs | - | - | - | - | - |
| Rapports | Stats ses classes | - | - | - | OK |
| Journal activite | - | - | - | - | - |

---

### 6. Surveillant

**Description** : Role operationnel de terrain. Consulte les listes d'eleves et gere les abonnements bus/cantine.

| Module | Lecture | Ecriture | Suppression | Export | Impression |
|--------|---------|----------|-------------|--------|------------|
| Eleves | OK (lecture) | - | - | - | - |
| Notes | - | - | - | - | - |
| Paiements | - | - | - | - | - |
| Depenses | - | - | - | - | - |
| Salaires | - | - | - | - | - |
| Abonnements | OK | OK | - | - | - |
| Administration | - | - | - | - | - |
| Utilisateurs | - | - | - | - | - |
| Rapports | - | - | - | - | - |
| Journal activite | - | - | - | - | - |

---

## Gestion des permissions par menu

Les permissions sont stockees dans le champ `allowed_menus` (JSONField) du modele `Profil`. Chaque entree represente une section de l'interface accessible a l'utilisateur.

Exemple de configuration JSON :
```json
{
  "eleves": ["liste", "ajouter", "modifier", "carte", "export"],
  "notes": ["liste", "saisie", "bulletin"],
  "paiements": ["liste", "ajouter", "recu"],
  "rapports": ["effectifs"]
}
```

---

## Audit et traçabilite

### Journal d'activite (JournalActivite)

Toutes les actions importantes sont enregistrees automatiquement :

| Type d'action | Declencheur |
|---------------|-------------|
| `LOGIN` | Connexion reussie |
| `LOGOUT` | Deconnexion |
| `CREATE` | Creation d'un enregistrement |
| `UPDATE` | Modification d'un enregistrement |
| `DELETE` | Suppression d'un enregistrement |
| `EXPORT` | Export Excel ou PDF |
| `PRINT` | Impression de document |
| `VIEW` | Consultation d'une fiche sensible |

Chaque entree du journal contient :
- Identifiant de l'utilisateur
- Type d'action
- Module concerne
- Description de l'action
- Horodatage (date + heure)
- Adresse IP du client
- User-Agent du navigateur

### Sessions utilisateur (SessionUtilisateur)

- Suivi de chaque session de connexion
- IP d'origine enregistree
- Duree de la session
- Derniere activite

---

## Creation et gestion des comptes

### Creer un nouveau compte utilisateur

1. Se connecter en tant qu'Administrateur
2. Aller dans **Utilisateurs > Gestion des comptes**
3. Cliquer **Ajouter un utilisateur**
4. Remplir le formulaire :
   - Nom d'utilisateur (unique)
   - Mot de passe (minimum 8 caracteres)
   - Prenom et nom
   - Email
   - Role
   - Ecole rattachee (si applicable)
5. Confirmer la creation

### Modifier les permissions

1. Aller dans **Utilisateurs > Gestion des comptes**
2. Cliquer sur l'utilisateur a modifier
3. Modifier le role ou les permissions specifiques
4. Sauvegarder

### Desactiver un compte

1. Aller dans la fiche de l'utilisateur
2. Cliquer **Desactiver le compte**
3. L'utilisateur ne peut plus se connecter mais ses donnees sont conservees

---

## Securite des mots de passe

- Longueur minimale : 8 caracteres
- Hashage : PBKDF2 avec SHA-256 (standard Django)
- Un utilisateur peut changer son propre mot de passe depuis son profil
- Un Administrateur peut reinitialiser le mot de passe de n'importe quel utilisateur

---

## Bonnes pratiques de securite

1. **Principe du moindre privilege** : Attribuer le role le moins privilegie qui couvre le besoin de l'utilisateur
2. **Un compte par personne** : Ne pas partager de comptes entre plusieurs utilisateurs
3. **Revue periodique** : Verifier regulierement les comptes actifs et supprimer les comptes inutiles
4. **Mots de passe forts** : Encourager l'utilisation de mots de passe complexes
5. **Deconnexion** : Se deconnecter apres utilisation, surtout sur des postes partages
