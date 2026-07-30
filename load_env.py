import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

def _load_plain_env(path):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip())


# Charger les variables d'environnement depuis .env et depuis le .env global PythonAnywhere.
env_paths = [
    Path('/home/myschoolgn/.env'),
    Path.cwd() / '.env',
]

for env_path in env_paths:
    if load_dotenv:
        load_dotenv(env_path, override=False)
    else:
        _load_plain_env(env_path)
