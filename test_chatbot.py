"""
Script de test pour vérifier l'installation du chatbot
Usage: python test_chatbot.py
"""
import os
import sys
import django

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecole_moderne.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from chatbot.models import Matiere, DocumentCours
from chatbot.search_engine import extraire_mots_cles, rechercher_dans_documents

def test_matieres():
    """Test des matières"""
    print("\n=== Test des Matieres ===")
    matieres = Matiere.objects.filter(actif=True)
    print(f"Nombre de matieres: {matieres.count()}")
    for m in matieres[:5]:
        print(f"  - {m.icone} {m.nom}")
    return matieres.count() > 0

def test_extraction_mots_cles():
    """Test de l'extraction de mots-clés"""
    print("\n=== Test Extraction Mots-Cles ===")
    questions = [
        "Qu'est-ce que le théorème de Pythagore ?",
        "Expliquer la photosynthèse",
        "Les causes de la Révolution française"
    ]
    for q in questions:
        mots = extraire_mots_cles(q)
        print(f"  Q: {q}")
        print(f"  Mots-cles: {mots}")
    return True

def test_recherche():
    """Test de la recherche"""
    print("\n=== Test Recherche ===")
    resultats = rechercher_dans_documents("mathematiques")
    print(f"Resultats pour 'mathematiques': {len(resultats)}")
    return True

def test_documents():
    """Test des documents"""
    print("\n=== Test Documents ===")
    docs = DocumentCours.objects.filter(actif=True)
    print(f"Nombre de documents: {docs.count()}")
    for d in docs[:3]:
        print(f"  - {d.titre} ({d.matiere.nom})")
    return True

def main():
    print("=" * 50)
    print("TEST DU CHATBOT DE REVISION")
    print("=" * 50)
    
    tests = [
        ("Matieres", test_matieres),
        ("Extraction mots-cles", test_extraction_mots_cles),
        ("Recherche", test_recherche),
        ("Documents", test_documents),
    ]
    
    resultats = []
    for nom, test_func in tests:
        try:
            success = test_func()
            resultats.append((nom, "OK" if success else "ECHEC"))
        except Exception as e:
            resultats.append((nom, f"ERREUR: {e}"))
    
    print("\n" + "=" * 50)
    print("RESULTATS")
    print("=" * 50)
    for nom, status in resultats:
        print(f"  {nom}: {status}")
    
    print("\n" + "=" * 50)
    print("URLs disponibles:")
    print("  - http://127.0.0.1:8001/chatbot/")
    print("  - http://127.0.0.1:8001/chatbot/chat/")
    print("  - http://127.0.0.1:8001/chatbot/documents/")
    print("  - http://127.0.0.1:8001/chatbot/admin/documents/")
    print("=" * 50)

if __name__ == "__main__":
    main()
