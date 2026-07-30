"""
Commande Django pour optimiser les performances du projet
Usage: python manage.py optimize_performance
"""
from django.core.management.base import BaseCommand
from django.db import connection
from django.core.cache import cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Optimise les performances du projet École Moderne'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-indexes',
            action='store_true',
            help='Crée les index de base de données recommandés',
        )
        parser.add_argument(
            '--clear-cache',
            action='store_true',
            help='Vide tous les caches',
        )
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Pré-charge les caches importants',
        )
        parser.add_argument(
            '--analyze-queries',
            action='store_true',
            help='Analyse les requêtes lentes',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Exécute toutes les optimisations',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🚀 Début de l\'optimisation des performances...')
        )

        if options['all']:
            options['create_indexes'] = True
            options['clear_cache'] = True
            options['warm_cache'] = True
            options['analyze_queries'] = True

        if options['create_indexes']:
            self.create_database_indexes()

        if options['clear_cache']:
            self.clear_all_caches()

        if options['warm_cache']:
            self.warm_up_caches()

        if options['analyze_queries']:
            self.analyze_database_queries()

        self.stdout.write(
            self.style.SUCCESS('✅ Optimisation des performances terminée!')
        )

    def create_database_indexes(self):
        """Crée les index de base de données recommandés"""
        self.stdout.write('📊 Création des index de base de données...')
        
        from ecole_moderne.performance_settings import RECOMMENDED_DATABASE_INDEXES
        
        with connection.cursor() as cursor:
            created_count = 0
            for index_sql in RECOMMENDED_DATABASE_INDEXES:
                try:
                    cursor.execute(index_sql)
                    created_count += 1
                    self.stdout.write(f'  ✓ Index créé: {index_sql[:50]}...')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Erreur index: {e}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'📊 {created_count} index créés avec succès')
            )

    def clear_all_caches(self):
        """Vide tous les caches"""
        self.stdout.write('🧹 Nettoyage des caches...')
        
        try:
            cache.clear()
            self.stdout.write(self.style.SUCCESS('🧹 Tous les caches ont été vidés'))
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors du nettoyage des caches: {e}')
            )

    def warm_up_caches(self):
        """Pré-charge les caches importants"""
        self.stdout.write('🔥 Pré-chargement des caches...')
        
        try:
            from ecole_moderne.query_optimizer import QueryOptimizer
            from django.contrib.auth.models import User
            
            # Pré-charger les caches pour les utilisateurs actifs
            active_users = User.objects.filter(is_active=True)[:10]  # Limiter à 10
            
            warmed_count = 0
            for user in active_users:
                try:
                    QueryOptimizer.warm_up_cache(user)
                    warmed_count += 1
                    self.stdout.write(f'  ✓ Cache pré-chargé pour utilisateur {user.id}')
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'  ⚠️  Erreur cache utilisateur {user.id}: {e}')
                    )
            
            self.stdout.write(
                self.style.SUCCESS(f'🔥 Caches pré-chargés pour {warmed_count} utilisateurs')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors du pré-chargement: {e}')
            )

    def analyze_database_queries(self):
        """Analyse les requêtes de base de données"""
        self.stdout.write('🔍 Analyse des requêtes de base de données...')
        
        try:
            with connection.cursor() as cursor:
                # Analyser les tables les plus utilisées
                cursor.execute("""
                    SELECT table_name, table_rows, data_length, index_length
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE()
                    ORDER BY table_rows DESC
                    LIMIT 10
                """)
                
                results = cursor.fetchall()
                
                self.stdout.write('📈 Top 10 des tables par nombre de lignes:')
                for row in results:
                    table_name, rows, data_size, index_size = row
                    self.stdout.write(
                        f'  • {table_name}: {rows} lignes, '
                        f'Données: {self.format_bytes(data_size)}, '
                        f'Index: {self.format_bytes(index_size)}'
                    )
                
                # Vérifier les requêtes lentes (si le slow query log est activé)
                try:
                    cursor.execute("SHOW VARIABLES LIKE 'slow_query_log'")
                    slow_log_status = cursor.fetchone()
                    if slow_log_status and slow_log_status[1] == 'ON':
                        self.stdout.write('✅ Le log des requêtes lentes est activé')
                    else:
                        self.stdout.write(
                            self.style.WARNING('⚠️  Le log des requêtes lentes n\'est pas activé')
                        )
                except:
                    pass
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de l\'analyse: {e}')
            )

    def format_bytes(self, bytes_value):
        """Formate les bytes en unités lisibles"""
        if bytes_value is None:
            return '0 B'
        
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} TB"

    def get_performance_recommendations(self):
        """Génère des recommandations de performance"""
        recommendations = []
        
        # Vérifier la configuration du cache
        if not hasattr(settings, 'CACHES') or 'default' not in settings.CACHES:
            recommendations.append(
                "🔧 Configurez un système de cache (Redis ou Memcached) pour de meilleures performances"
            )
        
        # Vérifier la configuration de la base de données
        if hasattr(settings, 'DATABASES'):
            db_config = settings.DATABASES.get('default', {})
            if 'CONN_MAX_AGE' not in db_config or db_config['CONN_MAX_AGE'] == 0:
                recommendations.append(
                    "🔧 Activez les connexions persistantes à la base de données (CONN_MAX_AGE)"
                )
        
        # Vérifier les middlewares
        if hasattr(settings, 'MIDDLEWARE'):
            if 'django.middleware.cache.UpdateCacheMiddleware' not in settings.MIDDLEWARE:
                recommendations.append(
                    "🔧 Ajoutez le middleware de cache pour améliorer les performances des vues"
                )
        
        if recommendations:
            self.stdout.write('\n💡 Recommandations de performance:')
            for rec in recommendations:
                self.stdout.write(f'  {rec}')
        else:
            self.stdout.write('✅ Configuration de performance optimale détectée!')

    def display_performance_summary(self):
        """Affiche un résumé des performances"""
        self.stdout.write('\n📊 Résumé des performances:')
        
        try:
            from django.db import connection
            from django.core.cache import cache
            
            # Test du cache
            cache_test_key = 'performance_test'
            cache.set(cache_test_key, 'test_value', 10)
            cache_works = cache.get(cache_test_key) == 'test_value'
            cache.delete(cache_test_key)
            
            self.stdout.write(f'  • Cache: {"✅ Fonctionnel" if cache_works else "❌ Non fonctionnel"}')
            
            # Test de la base de données
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                db_works = cursor.fetchone()[0] == 1
            
            self.stdout.write(f'  • Base de données: {"✅ Fonctionnelle" if db_works else "❌ Non fonctionnelle"}')
            
        except Exception as e:
            self.stdout.write(f'  ❌ Erreur lors du test: {e}')
