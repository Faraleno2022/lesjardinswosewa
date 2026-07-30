"""
Configuration des paramètres Django pour optimiser les performances
À inclure dans settings.py pour améliorer les performances globales
"""

# Configuration du cache
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
        'TIMEOUT': 300,  # 5 minutes par défaut
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
            'CULL_FREQUENCY': 3,
        }
    },
    'session': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'session-cache',
        'TIMEOUT': 1800,  # 30 minutes pour les sessions
    }
}

# Configuration des sessions avec cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'session'
SESSION_COOKIE_AGE = 1800  # 30 minutes

# Optimisations de base de données
DATABASES_OPTIMIZATION = {
    'default': {
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            'charset': 'utf8mb4',
            'use_unicode': True,
        },
        'CONN_MAX_AGE': 600,  # Connexions persistantes
    }
}

# Middleware optimisé (ordre important pour les performances)
PERFORMANCE_MIDDLEWARE = [
    'django.middleware.cache.UpdateCacheMiddleware',  # Cache en premier
    'ecole_moderne.middleware.PerformanceMiddleware',  # Notre middleware de performance
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'ecole_moderne.middleware.CacheControlMiddleware',  # Contrôle du cache
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'ecole_moderne.middleware.DatabaseOptimizationMiddleware',  # Optimisation DB
    'django.middleware.cache.FetchFromCacheMiddleware',  # Cache en dernier
]

# Configuration du cache de templates
TEMPLATE_OPTIMIZATION = {
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [],
    'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
        'loaders': [
            ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]),
        ],
    },
}

# Configuration de logging pour le monitoring des performances
PERFORMANCE_LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'performance': {
            'format': '[{levelname}] {asctime} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'performance_file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': 'performance.log',
            'formatter': 'performance',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'performance',
        },
    },
    'loggers': {
        'ecole_moderne.middleware': {
            'handlers': ['performance_file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
        'ecole_moderne.query_optimizer': {
            'handlers': ['performance_file'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Configuration des fichiers statiques pour la production
STATIC_OPTIMIZATION = {
    'STATICFILES_STORAGE': 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage',
    'STATICFILES_FINDERS': [
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    ],
}

# Configuration de compression (si django-compressor est installé)
COMPRESS_OPTIMIZATION = {
    'COMPRESS_ENABLED': True,
    'COMPRESS_OFFLINE': True,
    'COMPRESS_CSS_FILTERS': [
        'compressor.filters.css_default.CssAbsoluteFilter',
        'compressor.filters.cssmin.rCSSMinFilter',
    ],
    'COMPRESS_JS_FILTERS': [
        'compressor.filters.jsmin.JSMinFilter',
    ],
}

# Paramètres de pagination par défaut
PAGINATION_SETTINGS = {
    'DEFAULT_PER_PAGE': 20,
    'MAX_PER_PAGE': 100,
    'ORPHANS': 3,  # Évite les pages avec très peu d'éléments
}

# Configuration des requêtes optimisées
DATABASE_QUERY_OPTIMIZATION = {
    'SELECT_RELATED_DEPTH': 2,  # Profondeur par défaut pour select_related
    'PREFETCH_RELATED_LOOKUPS': [
        'paiements',
        'eleves',
        'evaluations',
    ],
}

# Configuration du cache de vues
VIEW_CACHE_SETTINGS = {
    'CACHE_MIDDLEWARE_ALIAS': 'default',
    'CACHE_MIDDLEWARE_SECONDS': 300,  # 5 minutes
    'CACHE_MIDDLEWARE_KEY_PREFIX': 'ecole_moderne',
}

# Optimisations spécifiques aux modèles
MODEL_OPTIMIZATIONS = {
    'USE_L10N': False,  # Désactiver la localisation si pas nécessaire
    'USE_I18N': False,  # Désactiver l'internationalisation si pas nécessaire
    'USE_TZ': True,     # Garder les timezones
}

# Configuration des index de base de données recommandés
RECOMMENDED_DATABASE_INDEXES = [
    # Élèves
    "CREATE INDEX IF NOT EXISTS idx_eleves_classe ON eleves_eleve(classe_id);",
    "CREATE INDEX IF NOT EXISTS idx_eleves_statut ON eleves_eleve(statut);",
    "CREATE INDEX IF NOT EXISTS idx_eleves_matricule ON eleves_eleve(matricule);",
    "CREATE INDEX IF NOT EXISTS idx_eleves_nom ON eleves_eleve(nom);",
    
    # Paiements
    "CREATE INDEX IF NOT EXISTS idx_paiements_eleve ON paiements_paiement(eleve_id);",
    "CREATE INDEX IF NOT EXISTS idx_paiements_date ON paiements_paiement(date_paiement);",
    "CREATE INDEX IF NOT EXISTS idx_paiements_statut ON paiements_paiement(statut);",
    "CREATE INDEX IF NOT EXISTS idx_paiements_type ON paiements_paiement(type_paiement_id);",
    
    # Classes
    "CREATE INDEX IF NOT EXISTS idx_classes_ecole ON eleves_classe(ecole_id);",
    "CREATE INDEX IF NOT EXISTS idx_classes_niveau ON eleves_classe(niveau);",
    
    # Notes
    "CREATE INDEX IF NOT EXISTS idx_notes_eleve ON notes_note(eleve_id);",
    "CREATE INDEX IF NOT EXISTS idx_notes_matiere ON notes_note(matiere_id);",
    "CREATE INDEX IF NOT EXISTS idx_evaluations_matiere ON notes_evaluation(matiere_id);",
    
    # Journal d'activité
    "CREATE INDEX IF NOT EXISTS idx_journal_user ON utilisateurs_journalactivite(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_journal_date ON utilisateurs_journalactivite(date_creation);",
    "CREATE INDEX IF NOT EXISTS idx_journal_action ON utilisateurs_journalactivite(action);",
]

# Fonction pour appliquer les optimisations
def apply_performance_settings(settings_dict):
    """
    Applique les optimisations de performance aux settings Django
    """
    # Cache
    settings_dict['CACHES'] = CACHES
    settings_dict['SESSION_ENGINE'] = SESSION_ENGINE
    settings_dict['SESSION_CACHE_ALIAS'] = SESSION_CACHE_ALIAS
    settings_dict['SESSION_COOKIE_AGE'] = SESSION_COOKIE_AGE
    
    # Middleware
    if 'MIDDLEWARE' in settings_dict:
        # Insérer nos middlewares aux bonnes positions
        middleware = settings_dict['MIDDLEWARE'][:]
        
        # Ajouter le middleware de performance après le security
        if 'django.middleware.security.SecurityMiddleware' in middleware:
            idx = middleware.index('django.middleware.security.SecurityMiddleware')
            middleware.insert(idx + 1, 'ecole_moderne.middleware.PerformanceMiddleware')
        
        # Ajouter le middleware de cache control
        if 'django.middleware.common.CommonMiddleware' in middleware:
            idx = middleware.index('django.middleware.common.CommonMiddleware')
            middleware.insert(idx, 'ecole_moderne.middleware.CacheControlMiddleware')
        
        settings_dict['MIDDLEWARE'] = middleware
    
    # Templates avec cache
    if 'TEMPLATES' in settings_dict and settings_dict['TEMPLATES']:
        template_config = settings_dict['TEMPLATES'][0]
        if 'OPTIONS' in template_config:
            template_config['OPTIONS']['loaders'] = TEMPLATE_OPTIMIZATION['OPTIONS']['loaders']
    
    # Logging
    if 'LOGGING' not in settings_dict:
        settings_dict['LOGGING'] = PERFORMANCE_LOGGING
    else:
        # Fusionner avec la configuration existante
        existing_logging = settings_dict['LOGGING']
        existing_logging['loggers'].update(PERFORMANCE_LOGGING['loggers'])
    
    return settings_dict
