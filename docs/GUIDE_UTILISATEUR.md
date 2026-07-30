# Guide Utilisateur - MySchoolGN

## Prise en main rapide

### Connexion au systeme

1. Ouvrir le navigateur et aller sur l'adresse du systeme (ou lancer l'executable MySchoolGN.exe)
2. Sur la page de connexion, saisir votre **nom d'utilisateur** et **mot de passe**
3. Cliquer **Se connecter**

Apres connexion, vous arrivez sur le **tableau de bord** qui affiche un resume de l'activite de l'ecole.

### Navigation

La barre de navigation en haut de la page contient les menus principaux. Seuls les menus auxquels vous avez acces sont visibles selon votre role.

---

## Guide par profil utilisateur

---

### Secretaire : Operations quotidiennes

#### Inscrire un nouvel eleve

1. Aller dans **Eleves > Ajouter un eleve**
2. Remplir le formulaire :
   - **Informations personnelles** : Prenom, nom, date et lieu de naissance, sexe
   - **Scolarite** : Ecole, classe, annee d'inscription
   - **Photo** : Uploader une photo (JPG/PNG, recommande 200x200px)
   - **Responsable** : Choisir un responsable existant ou en creer un nouveau
3. Cliquer **Enregistrer**
4. Le matricule est genere automatiquement

**Note** : Le matricule suit le format `[PREFIXE][ANNEE][SEQUENCE]`. Exemple : `GS2024001`

#### Editer la carte scolaire d'un eleve

1. Aller sur la fiche de l'eleve (via **Eleves > Liste** puis cliquer sur l'eleve)
2. Cliquer **Carte scolaire (PDF)**
3. Le PDF s'ouvre dans un nouvel onglet - l'imprimer ou le telecharger

#### Enregistrer un paiement

1. Aller dans **Paiements > Ajouter un paiement**
2. Selectionner l'eleve (recherche par nom ou matricule)
3. Choisir le type de paiement (Inscription, Scolarite, etc.)
4. Saisir le montant et le mode de paiement
5. Cliquer **Enregistrer**
6. Le recu est genere automatiquement - cliquer **Imprimer le recu** pour l'editer

#### Importer des eleves depuis Excel

1. Aller dans **Eleves > Importer depuis Excel**
2. Telecharger le modele Excel (lien sur la page)
3. Remplir le fichier Excel avec les donnees des eleves
4. Uploader le fichier et cliquer **Importer**
5. Verifier le rapport d'import (erreurs eventuelles signalees)

---

### Enseignant : Saisie des notes

#### Saisir les notes d'une evaluation

1. Aller dans **Notes > Saisie des notes**
2. Selectionner votre **classe** et votre **matiere**
3. Selectionner la **periode** (trimestre ou mois)
4. Selectionner le **type d'evaluation** (Devoir, Composition, Examen)
5. Saisir les notes pour chaque eleve dans le tableau
6. Cliquer **Enregistrer les notes**

**Conseil** : Utilisez la touche Tab pour passer d'une note a la suivante rapidement.

#### Consulter les bulletins de sa classe

1. Aller dans **Notes > Bulletins**
2. Selectionner la classe et la periode
3. Cliquer **Apercu** pour voir un bulletin en ligne
4. Cliquer **Imprimer** pour generer le PDF

#### Imprimer tous les bulletins d'une classe

1. Aller dans **Notes > Bulletins**
2. Selectionner la classe et la periode
3. Cliquer **Imprimer tous les bulletins**
4. Un fichier PDF unique est genere avec tous les bulletins de la classe

---

### Comptable : Gestion financiere

#### Tableau de bord financier

Le tableau de bord Paiements affiche :
- **Recettes du mois** : Total des paiements recus
- **Eleves en retard** : Liste des eleves avec des echeances impayees
- **Taux de recouvrement** : Pourcentage des paiements recus vs dus

#### Gestion des echeanciers de paiement

1. Aller dans **Paiements > Echeanciers**
2. Selectionner l'eleve
3. Definir le calendrier de paiement (montant par mensualite, dates d'echeance)
4. Sauvegarder

#### Paiement partiel

Le systeme gere automatiquement les paiements partiels :
- Si un eleve paie moins que le montant du, le systeme alloue d'abord aux echeances les plus anciennes
- Le solde restant est affiche sur la fiche de l'eleve
- Voir `docs/GUIDE_PAIEMENT_PARTIEL_INTELLIGENT.md` pour le detail

#### Enregistrer une depense

1. Aller dans **Depenses > Ajouter une depense**
2. Remplir :
   - Libelle de la depense
   - Montant
   - Categorie (Fournitures, Entretien, etc.)
   - Fournisseur (optionnel)
   - Piece justificative (photo de la facture)
3. Enregistrer - la depense passe en statut "En attente de validation"
4. Le Directeur ou l'Administrateur la validera

#### Exporter les paiements en Excel

1. Aller dans **Paiements > Liste**
2. Appliquer les filtres souhaites (periode, classe, type)
3. Cliquer **Exporter en Excel**
4. Le fichier se telecharge automatiquement

---

### Directeur : Supervision et rapports

#### Tableau de bord de direction

Le tableau de bord affiche :
- Effectifs par classe
- Paiements du jour/mois
- Eleves avec retards de paiement
- Derniers bulletins imprimes
- Alertes et notifications

#### Valider une depense

1. Aller dans **Depenses > En attente de validation**
2. Cliquer sur la depense a examiner
3. Consulter les details et la piece justificative
4. Cliquer **Approuver** ou **Rejeter** avec un commentaire

#### Consulter les rapports

1. Aller dans **Rapports**
2. Choisir le type de rapport :
   - **Financier** : Recettes et depenses par periode
   - **Effectifs** : Nombre d'eleves par classe
   - **Paiements** : Etat des paiements, retards
   - **Pedagogique** : Resultats scolaires par classe
3. Definir les filtres de periode
4. Cliquer **Generer** pour afficher
5. **Exporter PDF** ou **Exporter Excel** selon le besoin

---

### Administrateur : Configuration systeme

#### Configurer les informations de l'ecole

1. Aller dans **Administration > Parametres de l'ecole**
2. Renseigner :
   - Nom de l'ecole
   - Adresse et contacts
   - Logo (image PNG recommandee, 300x100px)
   - Prefixe pour les matricules
3. Sauvegarder

#### Gerer les classes

1. Aller dans **Eleves > Classes**
2. Pour ajouter une classe :
   - Cliquer **Ajouter une classe**
   - Saisir le nom, le niveau (Maternelle/Primaire/Secondaire)
   - Associer a une ecole
3. Pour modifier : cliquer sur la classe dans la liste

#### Gerer les grilles tarifaires

1. Aller dans **Eleves > Grilles tarifaires**
2. Selectionner l'ecole et la classe
3. Definir les montants :
   - Frais d'inscription
   - Scolarite mensuelle
   - Frais divers eventuels
4. Sauvegarder

#### Consulter le journal d'activite

1. Aller dans **Utilisateurs > Journal d'activite**
2. Filtrer par :
   - Utilisateur
   - Type d'action (Connexion, Creation, Modification, etc.)
   - Periode
   - Module
3. Exporter si necessaire pour audit

---

## Fonctionnalites communes

### Recherche rapide

La barre de recherche en haut permet de trouver rapidement un eleve par :
- Nom ou prenom
- Matricule
- Classe

### Notifications et alertes

Le systeme affiche automatiquement des alertes pour :
- Paiements en retard (> 30 jours)
- Licence arrivant a expiration
- Erreurs de saisie

### Aide du Chatbot

En bas a droite de chaque page, une icone de chatbot permet d'ouvrir l'assistant IA.
Vous pouvez lui poser des questions comme :
- "Comment inscrire un eleve ?"
- "Combien d'eleves sont en CM1 ?"
- "Quel est le taux de paiement ce mois ?"

---

## Gestion des documents

### Bulletins scolaires

Les bulletins sont generes en PDF et incluent :
- En-tete avec logo et nom de l'ecole
- Informations de l'eleve (nom, classe, annee)
- Tableau des notes par matiere avec coefficient
- Moyenne generale et rang dans la classe
- Mention et appreciation du directeur
- Zones de signature (directeur, parents)

**Cycles supportes :**
- **Maternelle** : Appreication par competences (Acquis/En cours/Non acquis)
- **Primaire** : Notes sur 10 ou 20, appreciation
- **Secondaire** : Notes sur 20, coefficients, moyenne, rang, mention

### Recus de paiement

Les recus incluent :
- Numero unique (format RECANNEExxxxx)
- Informations de l'ecole
- Nom et matricule de l'eleve
- Montant, mode et type de paiement
- Date et cachet

### Carte scolaire

La carte scolaire inclut :
- Photo de l'eleve
- Nom, classe, annee scolaire
- Matricule et informations de l'ecole
- Format recto (ID card)

---

## Questions frequentes (FAQ)

**Q : Comment reinitialiser mon mot de passe ?**
R : Contacter l'Administrateur du systeme. Il peut reinitialiser votre mot de passe depuis **Utilisateurs > Gestion des comptes**.

**Q : Je ne vois pas certains menus. Pourquoi ?**
R : Votre role ne vous donne pas acces a ces modules. Contacter l'Administrateur si vous avez besoin d'un acces supplementaire.

**Q : Comment changer d'annee scolaire ?**
R : Aller dans **Administration > Annee scolaire** et mettre a jour l'annee en cours. Attention : cette operation affecte tout le systeme.

**Q : L'application affiche "Licence invalide". Que faire ?**
R : La licence de l'application a expire ou est absente. Contacter le support pour obtenir une nouvelle cle de licence, puis lancer `generate_license_gui.py`.

**Q : Comment retrouver un eleve archive ?**
R : Aller dans **Eleves > Archives**. Les eleves archives sont conserves mais n'apparaissent pas dans les listes actives.

**Q : Peut-on imprimer plusieurs bulletins a la fois ?**
R : Oui. Dans **Notes > Bulletins**, selectionner la classe et la periode, puis cliquer **Imprimer tous les bulletins**. Un PDF unique contenant tous les bulletins est genere.

**Q : Comment exporter les donnees pour un audit externe ?**
R : Chaque module dispose d'un bouton **Exporter en Excel**. Pour un rapport complet, aller dans **Rapports** et exporter le rapport financier ou pedagogique selon le besoin.
