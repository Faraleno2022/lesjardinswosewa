"""
Moteur de recherche pour le chatbot éducatif
Recherche dans les documents uploadés pour répondre aux questions
Intégration IA avec DeepSeek via HuggingFace
"""
import re
import unicodedata
import logging
from difflib import SequenceMatcher
from django.db.models import Q
from .models import DocumentCours, RecherchePopulaire

logger = logging.getLogger(__name__)


def normaliser_texte(texte):
    """Normalise le texte pour la recherche (accents, casse, etc.)"""
    if not texte:
        return ""
    # Convertir en minuscules
    texte = texte.lower()
    # Supprimer les accents
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    # Supprimer la ponctuation
    texte = re.sub(r'[^\w\s]', ' ', texte)
    # Supprimer les espaces multiples
    texte = re.sub(r'\s+', ' ', texte).strip()
    return texte


def extraire_mots_cles(question):
    """Extrait les mots-clés significatifs d'une question"""
    # Mots à ignorer (stop words français)
    stop_words = {
        'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'et', 'ou', 'mais',
        'donc', 'or', 'ni', 'car', 'que', 'qui', 'quoi', 'dont', 'où', 'quand',
        'comment', 'pourquoi', 'est', 'sont', 'était', 'étaient', 'être', 'avoir',
        'fait', 'faire', 'dit', 'dire', 'peut', 'peuvent', 'pouvoir', 'doit',
        'doivent', 'devoir', 'ce', 'cette', 'ces', 'cet', 'mon', 'ma', 'mes',
        'ton', 'ta', 'tes', 'son', 'sa', 'ses', 'notre', 'nos', 'votre', 'vos',
        'leur', 'leurs', 'je', 'tu', 'il', 'elle', 'nous', 'vous', 'ils', 'elles',
        'me', 'te', 'se', 'lui', 'en', 'y', 'ne', 'pas', 'plus', 'moins', 'très',
        'bien', 'mal', 'tout', 'tous', 'toute', 'toutes', 'quel', 'quelle', 'quels',
        'quelles', 'avec', 'sans', 'pour', 'par', 'sur', 'sous', 'dans', 'entre',
        'vers', 'chez', 'avant', 'après', 'pendant', 'depuis', 'jusqu', 'jusque',
        'moi', 'toi', 'soi', 'eux', 'cela', 'ceci', 'ca', 'ça', 'si', 'alors',
        'aussi', 'encore', 'toujours', 'jamais', 'rien', 'personne', 'quelque',
        'quelques', 'chaque', 'autre', 'autres', 'même', 'mêmes', 'tel', 'telle',
        'tels', 'telles', 'peu', 'beaucoup', 'trop', 'assez', 'combien', 'fois',
        'c\'est', 'qu\'est', 'expliquer', 'expliquez', 'definir', 'definissez',
        'donner', 'donnez', 'citer', 'citez', 'enumerer', 'enumerez'
    }
    
    texte_normalise = normaliser_texte(question)
    mots = texte_normalise.split()
    
    # Filtrer les mots courts et les stop words
    mots_cles = [mot for mot in mots if len(mot) > 2 and mot not in stop_words]
    
    return mots_cles


def calculer_score_pertinence(texte_document, mots_cles):
    """Calcule un score de pertinence entre un document et les mots-clés"""
    if not texte_document or not mots_cles:
        return 0
    
    texte_normalise = normaliser_texte(texte_document)
    score = 0
    
    for mot in mots_cles:
        # Recherche exacte
        if mot in texte_normalise:
            score += 10
            # Bonus pour les occurrences multiples
            occurrences = texte_normalise.count(mot)
            score += min(occurrences - 1, 5)  # Max 5 points bonus
        else:
            # Recherche approximative (similarité)
            mots_document = texte_normalise.split()
            for mot_doc in mots_document:
                ratio = SequenceMatcher(None, mot, mot_doc).ratio()
                if ratio > 0.8:  # 80% de similarité
                    score += 5
                    break
    
    return score


def extraire_passage_pertinent(texte, mots_cles, longueur_max=500):
    """Extrait le passage le plus pertinent contenant les mots-clés"""
    if not texte or not mots_cles:
        return texte[:longueur_max] if texte else ""
    
    texte_normalise = normaliser_texte(texte)
    meilleur_debut = 0
    meilleur_score = 0
    
    # Découper en phrases
    phrases = re.split(r'[.!?]\s+', texte)
    
    for i, phrase in enumerate(phrases):
        phrase_norm = normaliser_texte(phrase)
        score = sum(1 for mot in mots_cles if mot in phrase_norm)
        if score > meilleur_score:
            meilleur_score = score
            meilleur_debut = i
    
    # Construire le passage autour de la meilleure phrase
    debut = max(0, meilleur_debut - 1)
    fin = min(len(phrases), meilleur_debut + 3)
    passage = '. '.join(phrases[debut:fin])
    
    if len(passage) > longueur_max:
        passage = passage[:longueur_max] + "..."
    
    return passage


def rechercher_dans_documents(question, matiere_id=None, niveau=None, limite=5):
    """
    Recherche les documents les plus pertinents pour une question
    
    Args:
        question: La question posée par l'utilisateur
        matiere_id: ID de la matière pour filtrer (optionnel)
        niveau: Niveau scolaire pour filtrer (optionnel)
        limite: Nombre maximum de résultats
    
    Returns:
        Liste de dictionnaires avec les résultats pertinents
    """
    mots_cles = extraire_mots_cles(question)
    
    if not mots_cles:
        return []
    
    # Construire la requête de base
    documents = DocumentCours.objects.filter(actif=True)
    
    if matiere_id:
        documents = documents.filter(matiere_id=matiere_id)
    
    if niveau:
        documents = documents.filter(Q(niveau=niveau) | Q(niveau='TOUS'))
    
    # Rechercher dans le titre, la description et le contenu extrait
    query = Q()
    for mot in mots_cles:
        query |= Q(titre__icontains=mot)
        query |= Q(description__icontains=mot)
        query |= Q(contenu_extrait__icontains=mot)
    
    documents = documents.filter(query).distinct()
    
    # Calculer les scores de pertinence
    resultats = []
    for doc in documents:
        texte_complet = f"{doc.titre} {doc.description} {doc.contenu_extrait}"
        score = calculer_score_pertinence(texte_complet, mots_cles)
        
        if score > 0:
            passage = extraire_passage_pertinent(doc.contenu_extrait, mots_cles)
            resultats.append({
                'document': doc,
                'score': score,
                'passage': passage,
                'mots_trouves': [mot for mot in mots_cles if mot in normaliser_texte(texte_complet)]
            })
    
    # Trier par score décroissant
    resultats.sort(key=lambda x: x['score'], reverse=True)
    
    return resultats[:limite]


def generer_reponse(question, resultats, utiliser_ia=True):
    """
    Génère une réponse formatée basée sur les résultats de recherche
    Utilise l'IA DeepSeek si disponible
    
    Args:
        question: La question originale
        resultats: Liste des résultats de recherche
        utiliser_ia: Activer/désactiver l'IA (défaut: True)
    
    Returns:
        Dictionnaire avec la réponse et les métadonnées
    """
    # Préparer les contextes des documents
    contextes = []
    for res in resultats[:3]:
        doc = res['document']
        passage = res['passage']
        if passage:
            contextes.append(f"[{doc.titre} - {doc.matiere.nom}]\n{passage}")
    
    # Essayer d'utiliser l'IA
    reponse_ia = None
    if utiliser_ia and (resultats or True):  # Toujours essayer l'IA
        try:
            from .ai_service import generer_reponse_ia
            matiere = resultats[0]['document'].matiere.nom if resultats else None
            reponse_ia = generer_reponse_ia(question, contextes, matiere)
        except Exception as e:
            logger.warning(f"Erreur IA, fallback mode classique: {e}")
    
    # Si l'IA a répondu
    if reponse_ia:
        confiance = 90 if resultats else 70
        
        # Ajouter les sources si disponibles
        if resultats:
            sources = "\n\n📚 **Sources consultées:**\n"
            for res in resultats[:3]:
                doc = res['document']
                sources += f"- {doc.titre} ({doc.matiere.nom})\n"
            reponse_ia += sources
        
        return {
            'reponse': reponse_ia,
            'documents': [r['document'] for r in resultats] if resultats else [],
            'confiance': confiance,
            'suggestions': generer_suggestions(question, resultats),
            'mode': 'ia'
        }
    
    # Fallback: Mode classique sans IA
    if not resultats:
        return {
            'reponse': "Je n'ai pas trouvé d'information pertinente dans les documents disponibles pour répondre à votre question. Essayez de reformuler votre question ou de sélectionner une matière spécifique.",
            'documents': [],
            'confiance': 0,
            'suggestions': [],
            'mode': 'classique'
        }
    
    # Construire la réponse classique
    meilleur_resultat = resultats[0]
    
    if meilleur_resultat['score'] >= 20:
        intro = "Voici ce que j'ai trouvé dans les documents de cours :\n\n"
        confiance = min(100, meilleur_resultat['score'] * 3)
    elif meilleur_resultat['score'] >= 10:
        intro = "J'ai trouvé des informations qui pourraient vous aider :\n\n"
        confiance = min(80, meilleur_resultat['score'] * 4)
    else:
        intro = "Voici quelques informations qui pourraient être liées à votre question :\n\n"
        confiance = min(50, meilleur_resultat['score'] * 5)
    
    # Formater les passages pertinents
    passages = []
    for i, res in enumerate(resultats[:3], 1):
        doc = res['document']
        passage = res['passage']
        if passage:
            passages.append(f"📖 **{doc.titre}** ({doc.matiere.nom})\n{passage}")
    
    reponse = intro + "\n\n".join(passages)
    
    # Ajouter une note sur les sources
    if len(resultats) > 1:
        reponse += f"\n\n📚 *{len(resultats)} document(s) trouvé(s) sur ce sujet.*"
    
    return {
        'reponse': reponse,
        'documents': [r['document'] for r in resultats],
        'confiance': confiance,
        'suggestions': generer_suggestions(question, resultats),
        'mode': 'classique'
    }


def generer_suggestions(question, resultats):
    """Génère des suggestions de questions liées"""
    suggestions = []
    
    if resultats:
        # Suggérer d'explorer les mêmes matières
        matieres = set(r['document'].matiere.nom for r in resultats)
        for matiere in list(matieres)[:2]:
            suggestions.append(f"Autres cours de {matiere}")
    
    # Suggestions génériques
    suggestions_generiques = [
        "Qu'est-ce que...",
        "Comment calculer...",
        "Expliquer le concept de...",
        "Donner un exemple de..."
    ]
    
    return suggestions[:4]


def enregistrer_recherche(question, matiere_id=None):
    """Enregistre une recherche pour les statistiques"""
    question_normalisee = normaliser_texte(question)[:500]
    
    recherche, created = RecherchePopulaire.objects.get_or_create(
        question=question_normalisee,
        matiere_id=matiere_id,
        defaults={'nombre_recherches': 1}
    )
    
    if not created:
        recherche.nombre_recherches += 1
        recherche.save()
    
    return recherche


def obtenir_suggestions_populaires(matiere_id=None, limite=5):
    """Retourne les recherches les plus populaires"""
    recherches = RecherchePopulaire.objects.all()
    
    if matiere_id:
        recherches = recherches.filter(Q(matiere_id=matiere_id) | Q(matiere__isnull=True))
    
    return list(recherches.values_list('question', flat=True)[:limite])
