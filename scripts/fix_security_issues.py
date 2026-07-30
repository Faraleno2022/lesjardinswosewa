#!/usr/bin/env python
"""
Script de correction automatique des vulnérabilités de sécurité
Usage: python scripts/fix_security_issues.py
"""

import os
import sys
import secrets
import string
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

def generate_secret_key(length=64):
    """Génère une SECRET_KEY Django sécurisée"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def create_env_file():
    """Crée un fichier .env sécurisé"""
    env_path = BASE_DIR / '.env'
    
    if env_path.exists():
        print("⚠️  Le fichier .env existe déjà.")
        response = input("Voulez-vous le remplacer? (o/N): ")
        if response.lower() != 'o':
            print("❌ Opération annulée.")
            return False
    
    secret_key = generate_secret_key()
    
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    env_content = f"""# Configuration de sécurité pour MySchool GN
# Généré automatiquement le {current_date}

# ===== SÉCURITÉ CRITIQUE =====
DJANGO_DEBUG=false
DJANGO_SECRET_KEY={secret_key}

# ===== BASE DE DONNÉES =====
DJANGO_DB_ENGINE=sqlite
# Pour MySQL, décommenter et configurer:
# DJANGO_DB_ENGINE=mysql
# DJANGO_DB_NAME=myschool_db
# DJANGO_DB_USER=myschool_user
# DJANGO_DB_PASSWORD=<mot_de_passe_fort>
# DJANGO_DB_HOST=localhost
# DJANGO_DB_PORT=3306

# ===== AUTHENTIFICATION =====
BLOCK_SUPERUSER_PUBLIC_LOGIN=true
MAX_LOGIN_ATTEMPTS=5
LOGIN_BLOCK_DURATION=300

# ===== TWILIO (SMS/WhatsApp) =====
TWILIO_ENABLED=false
# TWILIO_ACCOUNT_SID=<votre_sid>
# TWILIO_AUTH_TOKEN=<votre_token>
# TWILIO_PHONE_NUMBER=<votre_numero>

# ===== SÉCURITÉ AVANCÉE =====
IP_BLOCK_DURATION=86400
MAX_CONNECTIONS_PER_IP=10
ADMIN_WHITELIST_IPS=

# ===== EMAIL =====
# EMAIL_HOST=smtp.gmail.com
# EMAIL_PORT=587
# EMAIL_USE_TLS=true
# EMAIL_HOST_USER=<votre_email>
# EMAIL_HOST_PASSWORD=<mot_de_passe_app>
"""
    
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write(env_content)
    
    # Permissions restrictives (Unix/Linux)
    try:
        os.chmod(env_path, 0o600)
    except:
        pass
    
    print(f"✅ Fichier .env créé avec succès!")
    print(f"📁 Emplacement: {env_path}")
    print(f"🔑 SECRET_KEY générée (64 caractères)")
    print(f"\n⚠️  IMPORTANT: Ne JAMAIS commiter ce fichier sur Git!")
    
    return True

def update_gitignore():
    """Ajoute .env au .gitignore"""
    gitignore_path = BASE_DIR / '.gitignore'
    
    if not gitignore_path.exists():
        with open(gitignore_path, 'w') as f:
            f.write("# Fichiers de configuration sensibles\n")
    
    with open(gitignore_path, 'r') as f:
        content = f.read()
    
    if '.env' not in content:
        with open(gitignore_path, 'a') as f:
            f.write("\n# Variables d'environnement\n.env\n.env.local\n")
        print("✅ .env ajouté au .gitignore")
    else:
        print("ℹ️  .env déjà dans .gitignore")

def fix_twilio_csrf():
    """Corrige la vulnérabilité CSRF sur les webhooks Twilio"""
    views_path = BASE_DIR / 'paiements' / 'views.py'
    
    if not views_path.exists():
        print("❌ Fichier paiements/views.py non trouvé")
        return False
    
    with open(views_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Vérifier si la correction est déjà appliquée
    if 'RequestValidator' in content:
        print("ℹ️  Correction Twilio déjà appliquée")
        return True
    
    print("⚠️  Correction manuelle requise pour webhooks Twilio")
    print("📝 Voir RAPPORT_SECURITE.md section 'CRITIQUE 1'")
    
    return False

def check_dependencies():
    """Vérifie les dépendances vulnérables"""
    print("\n🔍 Vérification des dépendances...")
    
    try:
        import subprocess
        result = subprocess.run(
            ['pip', 'list', '--outdated'],
            capture_output=True,
            text=True
        )
        
        if result.stdout:
            print("⚠️  Packages obsolètes détectés:")
            print(result.stdout)
        else:
            print("✅ Toutes les dépendances sont à jour")
    except Exception as e:
        print(f"❌ Erreur lors de la vérification: {e}")

def create_security_checklist():
    """Crée une checklist de sécurité"""
    checklist_path = BASE_DIR / 'SECURITY_CHECKLIST.md'
    
    checklist_content = """# 🔒 CHECKLIST DE SÉCURITÉ - MySchool GN

## ✅ Configuration Initiale

- [ ] Fichier .env créé avec SECRET_KEY aléatoire
- [ ] DEBUG=false en production
- [ ] .env ajouté au .gitignore
- [ ] Permissions fichier .env: 600 (lecture/écriture propriétaire uniquement)

## ✅ Base de Données

- [ ] Backup automatique configuré
- [ ] Permissions db.sqlite3: 600
- [ ] Backup testé et fonctionnel

## ✅ Authentification

- [ ] Mots de passe administrateurs changés (12+ caractères)
- [ ] Limitation tentatives connexion testée
- [ ] Sessions expiration configurée (30 min)
- [ ] Blocage superuser login public activé

## ✅ HTTPS/Certificats

- [ ] Certificat SSL valide et actif
- [ ] HSTS activé (31536000 secondes)
- [ ] Redirection HTTP → HTTPS fonctionnelle
- [ ] Cookies SECURE activés

## ✅ Protection Attaques

- [ ] Middleware sécurité activé en production
- [ ] Rate limiting configuré
- [ ] CSRF protection testée
- [ ] XSS protection testée
- [ ] SQL Injection protection testée

## ✅ Logging/Monitoring

- [ ] Logs sécurité activés
- [ ] Rotation logs configurée
- [ ] Alertes administrateur configurées
- [ ] Monitoring erreurs 500 actif

## ✅ Backups

- [ ] Backup quotidien base de données
- [ ] Backup fichiers media
- [ ] Test restauration backup réussi
- [ ] Backup stocké hors serveur

## ✅ Mises à Jour

- [ ] Django à jour (dernière version stable)
- [ ] Dépendances Python à jour
- [ ] Système d'exploitation à jour
- [ ] Scanner vulnérabilités exécuté

## ✅ Tests de Sécurité

- [ ] Test SQL Injection effectué
- [ ] Test XSS effectué
- [ ] Test CSRF effectué
- [ ] Test Brute Force effectué
- [ ] Scan ports effectué

## ✅ Documentation

- [ ] Procédures incident sécurité documentées
- [ ] Contacts urgence définis
- [ ] Plan reprise activité créé
- [ ] Formation équipe sécurité effectuée

---

**Date dernière révision:** ___________  
**Responsable sécurité:** ___________  
**Prochaine révision:** ___________
"""
    
    with open(checklist_path, 'w', encoding='utf-8') as f:
        f.write(checklist_content)
    
    print(f"✅ Checklist créée: {checklist_path}")

def main():
    """Fonction principale"""
    print("=" * 60)
    print("🔒 CORRECTION AUTOMATIQUE DES VULNÉRABILITÉS DE SÉCURITÉ")
    print("=" * 60)
    print()
    
    # 1. Créer fichier .env
    print("📝 Étape 1: Création du fichier .env")
    create_env_file()
    print()
    
    # 2. Mettre à jour .gitignore
    print("📝 Étape 2: Mise à jour .gitignore")
    update_gitignore()
    print()
    
    # 3. Vérifier webhooks Twilio
    print("📝 Étape 3: Vérification webhooks Twilio")
    fix_twilio_csrf()
    print()
    
    # 4. Vérifier dépendances
    print("📝 Étape 4: Vérification des dépendances")
    check_dependencies()
    print()
    
    # 5. Créer checklist
    print("📝 Étape 5: Création de la checklist de sécurité")
    create_security_checklist()
    print()
    
    print("=" * 60)
    print("✅ CORRECTIONS TERMINÉES")
    print("=" * 60)
    print()
    print("📋 PROCHAINES ÉTAPES:")
    print("1. Lire RAPPORT_SECURITE.md pour détails complets")
    print("2. Lire SECURITY_CHECKLIST.md et cocher les items")
    print("3. Déployer sur PythonAnywhere avec .env configuré")
    print("4. Tester l'application en production")
    print("5. Exécuter: python manage.py check --deploy")
    print()
    print("⚠️  RAPPEL: Ne JAMAIS commiter .env sur Git!")
    print()

if __name__ == '__main__':
    main()
