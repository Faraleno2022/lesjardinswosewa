"""
Service IA pour le chatbot éducatif
Utilise DeepSeek via HuggingFace Router
"""
import os
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Configuration par défaut
DEFAULT_MODEL = "deepseek-ai/DeepSeek-R1"
HF_BASE_URL = "https://router.huggingface.co/v1"


def get_ai_client():
    """
    Initialise et retourne le client OpenAI configuré pour HuggingFace
    """
    try:
        from openai import OpenAI
        
        hf_token = getattr(settings, 'HF_TOKEN', None) or os.environ.get('HF_TOKEN')
        
        if not hf_token:
            logger.warning("HF_TOKEN non configuré - Mode IA désactivé")
            return None
        
        client = OpenAI(
            base_url=HF_BASE_URL,
            api_key=hf_token,
        )
        return client
    except ImportError:
        logger.error("Package 'openai' non installé. Installez avec: pip install openai")
        return None
    except Exception as e:
        logger.error(f"Erreur initialisation client IA: {e}")
        return None


def generer_reponse_ia(question, contexte_documents, matiere=None):
    """
    Génère une réponse intelligente basée sur les documents trouvés
    
    Args:
        question: La question de l'utilisateur
        contexte_documents: Liste des passages pertinents des documents
        matiere: Nom de la matière (optionnel)
    
    Returns:
        str: Réponse générée par l'IA ou None si erreur
    """
    client = get_ai_client()
    
    if not client:
        return None
    
    # Construire le contexte
    contexte = "\n\n".join(contexte_documents) if contexte_documents else ""

    # Contexte matière (si fourni) pour adapter la réponse
    matiere_str = f" de la matière {matiere}" if matiere else ""
    
    # Prompt système adapté à l'éducation
    system_prompt = f"""Tu es un professeur pédagogue pour les élèves du Groupe Scolaire Hadja Kanfing Diane en Guinée, spécialisé dans les cours{matiere_str}.

RÈGLES IMPORTANTES :
1. Réponds UNIQUEMENT en français.
2. Utilise un langage simple et adapté aux élèves du collège/lycée.
3. Base tes réponses en priorité sur le contexte fourni (extraits des documents de cours) quand il est disponible.
4. Si le contexte ne contient pas l'information nécessaire, dis-le clairement puis complète avec tes connaissances générales.
5. Sois encourageant et bienveillant.
6. Donne au moins un exemple concret (numérique ou situation réelle) quand c'est pertinent.
7. Structure tes réponses avec des phrases courtes et, si besoin, une petite liste de points clés.
8. Quand la question porte sur une notion mathématique (théorème, formule, définition), donne d'abord une explication simple, puis un exemple d'application.
9. Termine si possible par une phrase motivante pour l'élève (par exemple en l'encourageant à s'entraîner ou à relire son cours)."""

    # Construire le message utilisateur
    if contexte:
        user_message = f"""Contexte des documents de cours:
---
{contexte}
---

Question de l'élève: {question}

Réponds à la question en te basant sur le contexte ci-dessus. Si le contexte ne contient pas assez d'informations, complète avec tes connaissances mais précise-le."""
    else:
        user_message = f"""Question de l'élève: {question}

Note: Aucun document de cours n'a été trouvé sur ce sujet. Réponds avec tes connaissances générales mais encourage l'élève à consulter ses cours."""

    try:
        model = getattr(settings, 'HF_MODEL', DEFAULT_MODEL)
        
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            max_tokens=1024,
            temperature=0.7,
        )
        
        reponse = completion.choices[0].message.content
        return reponse
        
    except Exception as e:
        logger.error(f"Erreur génération réponse IA: {e}")
        return None


def verifier_configuration_ia():
    """
    Vérifie si l'IA est correctement configurée
    
    Returns:
        dict: Statut de la configuration
    """
    hf_token = getattr(settings, 'HF_TOKEN', None) or os.environ.get('HF_TOKEN')
    
    status = {
        'token_configure': bool(hf_token),
        'openai_installe': False,
        'connexion_ok': False,
        'message': ''
    }
    
    try:
        from openai import OpenAI
        status['openai_installe'] = True
    except ImportError:
        status['message'] = "Package 'openai' non installé"
        return status
    
    if not hf_token:
        status['message'] = "HF_TOKEN non configuré dans settings.py ou variables d'environnement"
        return status
    
    # Test de connexion
    try:
        client = OpenAI(base_url=HF_BASE_URL, api_key=hf_token)
        # Test simple
        completion = client.chat.completions.create(
            model=getattr(settings, 'HF_MODEL', DEFAULT_MODEL),
            messages=[{"role": "user", "content": "Test"}],
            max_tokens=10,
        )
        status['connexion_ok'] = True
        status['message'] = "Configuration IA OK"
    except Exception as e:
        status['message'] = f"Erreur connexion: {str(e)}"
    
    return status
