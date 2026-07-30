#!/usr/bin/env python
"""
Script pour analyser exactement le caractère dans l'erreur
"""

import urllib.parse

# Simuler l'URL exacte de l'erreur
url_param = "1%C2%A0874"
decoded_param = urllib.parse.unquote(url_param)

print("🔍 ANALYSE DU CARACTÈRE DANS L'ERREUR")
print("=" * 50)
print(f"URL paramètre : {url_param}")
print(f"Décodé : {repr(decoded_param)}")
print(f"Longueur : {len(decoded_param)}")

for i, char in enumerate(decoded_param):
    print(f"  Position {i}: '{char}' (U+{ord(char):04X})")

print("\n🧪 TEST AVEC DIFFÉRENTS ESPACES :")
espaces_test = [
    ("Espace normal", " "),
    ("Espace insécable UTF-8", "\xa0"),
    ("Unicode NBSP", "\u00A0"),
    ("Caractère de l'erreur", decoded_param[1]) if len(decoded_param) > 1 else ("N/A", "")
]

for nom, char in espaces_test:
    print(f"  {nom:<25}: {repr(char)} (U+{ord(char):04X})")

# Test avec regex
import re
print("\n🔧 TEST REGEX :")
test_regex = r'[\s\u00A0\u2000-\u200F\u2028-\u202F\u205F\u3000]'
print(f"Pattern: {test_regex}")
print(f"Match sur '{decoded_param}': {bool(re.search(test_regex, decoded_param))}")

# Test nettoyage manuel
param_nettoye = re.sub(test_regex, '', decoded_param)
print(f"Après nettoyage: '{param_nettoye}'")
print(f"Converti en int: {int(param_nettoye) if param_nettoye.isdigit() else 'ERREUR'}")
