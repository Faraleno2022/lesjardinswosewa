# Déploiement sur PythonAnywhere

Ce guide met à jour l'application depuis la branche `main` du dépôt
`Faraleno2022/lesjardinswosewa`. Le script refuse de migrer si Django est en
mode debug, si la clé secrète est faible ou si la base active n'est pas MySQL.

## 1. Configuration initiale

Dans une console Bash PythonAnywhere :

```bash
git clone https://github.com/Faraleno2022/lesjardinswosewa.git ~/myschool
mkvirtualenv --python=/usr/bin/python3.11 myschool
cd ~/myschool
python -m pip install -r requirements.txt
cp docs/env.example.txt .env
chmod 600 .env
```

Renseigner ensuite `~/myschool/.env` avec au minimum :

```dotenv
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<cle-aleatoire-forte>
DJANGO_ALLOWED_HOSTS=myschoolgn.pythonanywhere.com,myschoolgn.space,www.myschoolgn.space
DJANGO_CSRF_TRUSTED_ORIGINS=https://myschoolgn.pythonanywhere.com,https://myschoolgn.space,https://www.myschoolgn.space
DJANGO_DB_NAME=myschoolgn$myschooldb
DJANGO_DB_USER=myschoolgn
DJANGO_DB_PASSWORD=<mot-de-passe-mysql>
DJANGO_DB_HOST=myschoolgn.mysql.pythonanywhere-services.com
DJANGO_DB_PORT=3306
```

Adapter les valeurs au compte PythonAnywhere réel. Ne jamais ajouter `.env` à
Git ; ce fichier est déjà ignoré par le dépôt.

Une clé Django peut être générée sans l'afficher dans l'historique Bash :

```bash
workon myschool
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 2. Configuration de l'application Web

Dans l'onglet **Web** de PythonAnywhere :

- code source : `/home/<utilisateur>/myschool` ;
- virtualenv : `/home/<utilisateur>/.virtualenvs/myschool` ;
- fichier WSGI :

```python
import os
import sys

path = "/home/<utilisateur>/myschool"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecole_moderne.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

Mappings statiques :

| URL | Répertoire |
|---|---|
| `/static/` | `/home/<utilisateur>/myschool/staticfiles` |
| `/media/` | `/home/<utilisateur>/myschool/media` |

## 3. Sauvegarde avant mise à jour

Créer une sauvegarde MySQL avant les nouvelles migrations :

```bash
mkdir -p ~/backups
mysqldump -u <utilisateur_mysql> -h <hote_mysql> -p '<nom_base>' > ~/backups/myschool-$(date +%Y%m%d-%H%M%S).sql
```

Le mot de passe est demandé interactivement et n'apparaît pas dans la commande.

## 4. Publication

Depuis `~/myschool`, lancer :

```bash
PA_DOMAIN="myschoolgn.pythonanywhere.com" \
VENV_DIR="$HOME/.virtualenvs/myschool" \
bash scripts/deploy_pa.sh
```

`PA_DOMAIN` doit être le domaine PythonAnywhere de l'application Web, même si
les visiteurs utilisent principalement le domaine personnalisé.

Le script effectue, dans cet ordre :

1. mise à jour `main` en avance rapide uniquement ;
2. installation des dépendances dans le virtualenv ;
3. validation de la configuration de production ;
4. `manage.py check --deploy` ;
5. migrations MySQL ;
6. collecte des fichiers statiques ;
7. contrôle Django final ;
8. rechargement de l'application.

Pour inspecter sans récupérer Git ou sans recharger le site :

```bash
SKIP_GIT_PULL=1 SKIP_RELOAD=1 \
PA_DOMAIN="myschoolgn.pythonanywhere.com" \
VENV_DIR="$HOME/.virtualenvs/myschool" \
bash scripts/deploy_pa.sh
```

## 5. Vérifications après publication

Vérifier au minimum :

- `/utilisateurs/login/` ;
- `/paiements/liste/` : inscription et réinscription dans des colonnes séparées ;
- `/depenses/fournitures/` : tableau de bord des produits et ventes ;
- l'enregistrement d'une vente de test sans dépasser le stock ;
- l'export Excel du récapitulatif des paiements.

Les migrations attendues pour cette version sont :

```bash
workon myschool
cd ~/myschool
python manage.py showmigrations depenses paiements
```

- `depenses.0009_produitfourniture_ventefourniture_and_more` ;
- `paiements.0010_echeancier_nature_frais`.

Consulter enfin les journaux dans l'onglet **Web > Log files** et recharger
manuellement l'application si `pa_reload_webapp.py` n'est pas disponible.
