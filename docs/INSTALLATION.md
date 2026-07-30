# Guide d'installation et de deploiement - MySchoolGN

## Prerequis systeme

| Composant | Version minimale | Notes |
|-----------|-----------------|-------|
| Python | 3.10+ | Recommande : 3.11 |
| MySQL / MariaDB | 8.0+ / 10.6+ | Base de donnees principale |
| pip | 23+ | Gestionnaire de paquets Python |
| Git | 2.x | Gestion du code source |
| Windows 10/11 | - | Pour la version desktop .exe |

---

## Installation en developpement

### 1. Cloner le depot

```bash
git clone <url-du-depot>
cd GS_hadja_kanfing_dian--main
```

### 2. Creer l'environnement virtuel

```bash
# Creer
python -m venv venv

# Activer (Windows)
venv\Scripts\activate

# Activer (Linux/macOS)
source venv/bin/activate
```

### 3. Installer les dependances Python

```bash
pip install -r requirements.txt
```

**Dependances principales :**
```
Django==5.2.6
mysqlclient==2.2.7
reportlab==4.4.3
weasyprint==63.1
openpyxl==3.1.5
pandas>=2.0.0
openai>=1.0.0
Pillow==11.3.0
PyJWT==2.10.1
requests==2.32.5
twilio==9.8.1
python-dotenv
```

### 4. Configurer la base de donnees MySQL

```sql
-- Se connecter a MySQL en tant que root
CREATE DATABASE myschool_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'myschool_user'@'localhost' IDENTIFIED BY 'mot_de_passe_fort';
GRANT ALL PRIVILEGES ON myschool_db.* TO 'myschool_user'@'localhost';
FLUSH PRIVILEGES;
```

### 5. Configurer les variables d'environnement

Creer un fichier `.env` a la racine du projet :

```env
# Mode debug (mettre false en production)
DJANGO_DEBUG=true

# Cle secrete (OBLIGATOIRE - generer une cle unique en production)
DJANGO_SECRET_KEY=votre-cle-secrete-unique-ici

# Base de donnees
DB_NAME=myschool_db
DB_USER=myschool_user
DB_PASSWORD=mot_de_passe_fort
DB_HOST=localhost
DB_PORT=3306

# SMS Twilio (optionnel)
TWILIO_ENABLED=false
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# OpenAI pour le chatbot (optionnel)
OPENAI_API_KEY=
```

### 6. Appliquer les migrations

```bash
python manage.py migrate
```

### 7. Creer le superutilisateur

```bash
python manage.py createsuperuser
```

### 8. Collecter les fichiers statiques (production uniquement)

```bash
python manage.py collectstatic
```

### 9. Lancer le serveur de developpement

```bash
python manage.py runserver
```

L'application est accessible sur `http://127.0.0.1:8000/`

---

## Installation sur PythonAnywhere (production web)

### 1. Creer un compte PythonAnywhere

Se connecter sur [pythonanywhere.com](https://www.pythonanywhere.com) et creer un compte.

### 2. Uploader le code

Via la console Bash PythonAnywhere :
```bash
git clone <url-du-depot> ~/myschool
cd ~/myschool
pip install --user -r requirements.txt
```

### 3. Configurer la base de donnees MySQL

Dans le tableau de bord PythonAnywhere > Databases :
- Creer une base de donnees MySQL
- Noter les identifiants fournis

### 4. Configurer le fichier .env

```bash
nano ~/myschool/.env
```
Remplir avec les parametres de production (DEBUG=false, vraie SECRET_KEY, etc.)

### 5. Configurer l'application web

Dans le tableau de bord PythonAnywhere > Web :
- Cliquer "Add a new web app"
- Choisir "Manual configuration"
- Python 3.11

**WSGI file** (`/var/www/gshadjakanfingdiane_pythonanywhere_com_wsgi.py`) :
```python
import os
import sys

path = '/home/gshadjakanfingdiane/myschool'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'ecole_moderne.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

**Virtual environment** : `/home/gshadjakanfingdiane/.virtualenvs/myschool`

**Static files mapping** :
| URL | Directory |
|-----|-----------|
| `/static/` | `/home/gshadjakanfingdiane/myschool/staticfiles` |
| `/media/` | `/home/gshadjakanfingdiane/myschool/media` |

### 6. Appliquer les migrations et collecter les statiques

```bash
cd ~/myschool
python manage.py migrate
python manage.py collectstatic
```

### 7. Recharger l'application web

Dans le tableau de bord PythonAnywhere > Web, cliquer "Reload".

---

## Compilation de l'executable Windows (.exe)

### Prerequis supplementaires

- Installer GTK3 Runtime pour WeasyPrint (necessaire pour les DLLs)
- PyInstaller : `pip install pyinstaller`

### Compiler

```bash
python build_exe.py
```

L'executable est genere dans `dist/MySchoolGN/MySchoolGN.exe`.

### Structure du build

```
dist/
  MySchoolGN/
    MySchoolGN.exe          # Executable principal
    _internal/              # DLLs et ressources bundlees
      gtk/                  # DLLs GTK/Pango/Cairo
      static/               # Fichiers statiques
      templates/            # Templates HTML
      ...
```

### Generer une licence offline

```bash
python generate_license_gui.py
```

Ou en ligne de commande :
```bash
python license_manager.py --generate --school "Nom Ecole" --duration 365
```

---

## Verifications post-installation

### Verification de la base de donnees

```bash
python manage.py check --database default
```

### Verification generale

```bash
python manage.py check
```

### Verification de la configuration

```bash
python diagnostic_classes.py
```

---

## Mise a jour du systeme

```bash
# 1. Recuperer les nouvelles modifications
git pull origin main

# 2. Installer les nouvelles dependances si necessaire
pip install -r requirements.txt

# 3. Appliquer les nouvelles migrations
python manage.py migrate

# 4. Collecter les statiques (production)
python manage.py collectstatic --noinput

# 5. Recharger le serveur (production)
# PythonAnywhere : cliquer Reload dans le dashboard
```

---

## Resolution de problemes courants

### Erreur de connexion MySQL

```
django.db.utils.OperationalError: (2002, "Can't connect to MySQL server")
```

- Verifier que MySQL est bien demarre
- Verifier les parametres DB_HOST, DB_PORT, DB_USER, DB_PASSWORD dans .env

### Erreur WeasyPrint (DLLs manquantes)

```
OSError: cannot load library 'gobject-2.0-0'
```

- Installer GTK3 Runtime for Windows
- Verifier que les DLLs sont dans le PATH

### Erreur de licence

```
Acces bloque - Licence invalide ou expiree
```

- Lancer `generate_license_gui.py` pour generer une nouvelle licence
- Copier le fichier de licence dans le repertoire de l'application

### Port 8000 deja utilise

```bash
# Utiliser un autre port
python manage.py runserver 8080
```
