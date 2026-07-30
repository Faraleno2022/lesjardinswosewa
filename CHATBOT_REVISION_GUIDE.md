# 🤖 Chatbot de Révision - Guide Complet

## Description

Le **Chatbot de Révision** est un assistant éducatif intelligent qui permet aux élèves de réviser leurs cours en posant des questions. Le chatbot recherche les réponses dans les documents de cours uploadés par les enseignants.

## Fonctionnalités

### Pour les élèves
- 💬 **Chat interactif** : Posez des questions en langage naturel
- 📚 **Recherche intelligente** : Le chatbot cherche dans tous les documents
- 🎯 **Filtrage par matière** : Concentrez-vous sur une matière spécifique
- 📖 **Accès aux documents** : Consultez et téléchargez les cours
- 🔄 **Historique** : Retrouvez vos conversations précédentes

### Pour les administrateurs
- 📤 **Upload de documents** : PDF, Word (DOCX), TXT
- 📂 **Gestion des matières** : Créez et organisez les matières
- 📊 **Statistiques** : Suivez les consultations et recherches populaires
- ⚙️ **Administration** : Interface complète de gestion

## URLs

| URL | Description |
|-----|-------------|
| `/chatbot/` | Page d'accueil du chatbot |
| `/chatbot/chat/` | Interface de chat (toutes matières) |
| `/chatbot/chat/<id>/` | Chat pour une matière spécifique |
| `/chatbot/documents/` | Liste des documents disponibles |
| `/chatbot/documents/<id>/` | Détails d'un document |
| `/chatbot/admin/documents/` | Gestion des documents (staff) |
| `/chatbot/admin/documents/ajouter/` | Ajouter un document (staff) |
| `/chatbot/admin/matieres/` | Gestion des matières (staff) |

## Installation

### 1. Migrations
```bash
python manage.py makemigrations chatbot
python manage.py migrate chatbot
```

### 2. Initialiser les matières
```bash
python manage.py init_chatbot
```

### 3. Dépendances optionnelles (pour extraction de texte)
```bash
pip install PyPDF2  # Pour les PDF
pip install python-docx  # Pour les fichiers Word
```

## Formats de documents supportés

| Format | Extension | Bibliothèque requise |
|--------|-----------|---------------------|
| PDF | .pdf | PyPDF2 ou pdfplumber |
| Word | .docx | python-docx |
| Texte | .txt, .md | Aucune |

## Architecture

### Modèles
- **Matiere** : Catégories de cours (Maths, Français, etc.)
- **DocumentCours** : Documents uploadés avec contenu extrait
- **ConversationChat** : Sessions de chat
- **MessageChat** : Messages individuels
- **RecherchePopulaire** : Statistiques de recherche

### Fichiers principaux
```
chatbot/
├── models.py          # Modèles de données
├── views.py           # Vues et logique
├── urls.py            # Routes URL
├── admin.py           # Interface admin
├── search_engine.py   # Moteur de recherche
├── document_processor.py  # Extraction de texte
└── management/
    └── commands/
        └── init_chatbot.py  # Commande d'initialisation
```

### Templates
```
templates/chatbot/
├── home.html              # Page d'accueil
├── chat.html              # Interface de chat
├── documents.html         # Liste des documents
├── detail_document.html   # Détails document
├── gestion_documents.html # Admin documents
├── ajouter_document.html  # Formulaire ajout
└── gestion_matieres.html  # Admin matières
```

## Utilisation

### Ajouter un document
1. Connectez-vous en tant que staff
2. Allez sur `/chatbot/admin/documents/ajouter/`
3. Remplissez le formulaire (titre, matière, niveau)
4. Uploadez le fichier (PDF, DOCX, TXT)
5. Le contenu est automatiquement extrait

### Poser une question
1. Allez sur `/chatbot/chat/`
2. Sélectionnez une matière (optionnel)
3. Tapez votre question
4. Le chatbot recherche dans les documents
5. Recevez une réponse avec les sources

## API

### Envoyer un message
```
POST /chatbot/api/envoyer/
Content-Type: application/json

{
    "message": "Qu'est-ce que le théorème de Pythagore ?",
    "matiere_id": 1,  // optionnel
    "conversation_id": 5  // optionnel
}
```

### Réponse
```json
{
    "success": true,
    "reponse": "Voici ce que j'ai trouvé...",
    "confiance": 85,
    "documents": [
        {"id": 1, "titre": "Cours de géométrie", "matiere": "Mathématiques"}
    ],
    "suggestions": ["Autres cours de Mathématiques"]
}
```

## Personnalisation

### Ajouter des matières
Via l'interface `/chatbot/admin/matieres/` ou via la commande :
```python
from chatbot.models import Matiere
Matiere.objects.create(
    nom="Nouvelle Matière",
    icone="📚",
    description="Description"
)
```

### Modifier les seuils de confiance
Dans `search_engine.py`, fonction `generer_reponse()` :
- Score >= 20 : Haute confiance
- Score >= 10 : Confiance moyenne
- Score < 10 : Faible confiance

## Sécurité

- **Élèves** : Accès en lecture seule (chat, documents)
- **Staff** : Gestion complète (upload, suppression)
- **CSRF** : Protection sur toutes les requêtes POST
- **Validation** : Fichiers vérifiés (taille, format)

## Déploiement

### Production
1. Installer les dépendances sur le serveur :
```bash
pip install PyPDF2 python-docx
```

2. Collecter les fichiers statiques :
```bash
python manage.py collectstatic
```

3. Créer le dossier media :
```bash
mkdir -p media/chatbot/documents
```

4. Redémarrer le serveur :
```bash
touch ecole_moderne/wsgi.py
```

## Support

Pour toute question, consultez :
- Interface admin Django : `/admin/chatbot/`
- Logs : `logs/django.log`

---

**Version** : 1.0  
**Date** : Décembre 2024  
**Auteur** : Système de gestion scolaire G.S HKD
