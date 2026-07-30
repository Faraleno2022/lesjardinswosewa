"""
Commande Django pour envoyer automatiquement les rappels de paiement
Usage: python manage.py envoyer_rappels_paiement --canal SMS --limite 50
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.utils import timezone
from paiements.rappels import gestionnaire_rappels
from paiements.models import Relance

class Command(BaseCommand):
    help = 'Envoie automatiquement des rappels de paiement aux élèves en retard'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--canal',
            type=str,
            default='SMS',
            choices=['SMS', 'WHATSAPP', 'EMAIL', 'APPEL'],
            help='Canal de communication pour les rappels'
        )
        
        parser.add_argument(
            '--limite',
            type=int,
            default=50,
            help='Nombre maximum de rappels à créer'
        )
        
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulation sans créer de rappels'
        )
        
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force l\'envoi même si des rappels récents existent'
        )
        
        parser.add_argument(
            '--ecole-id',
            type=int,
            help='ID de l\'école (optionnel, pour filtrer)'
        )
    
    def handle(self, *args, **options):
        canal = options['canal']
        limite = options['limite']
        dry_run = options['dry_run']
        force = options['force']
        ecole_id = options['ecole_id']
        
        self.stdout.write(
            self.style.SUCCESS(f'🚀 Démarrage de l\'envoi des rappels de paiement')
        )
        self.stdout.write(f'Canal: {canal}')
        self.stdout.write(f'Limite: {limite}')
        self.stdout.write(f'Mode: {"Simulation" if dry_run else "Réel"}')
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('⚠️ MODE SIMULATION - Aucun rappel ne sera créé')
            )
        
        try:
            # Détecter les élèves en retard
            echeanciers_retard = gestionnaire_rappels.detecter_eleves_en_retard()
            
            if ecole_id:
                echeanciers_retard = echeanciers_retard.filter(eleve__classe__ecole_id=ecole_id)
                self.stdout.write(f'Filtrage par école ID: {ecole_id}')
            
            total_eleves_retard = echeanciers_retard.count()
            self.stdout.write(f'📊 {total_eleves_retard} élèves en retard détectés')
            
            if total_eleves_retard == 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Aucun élève en retard trouvé')
                )
                return
            
            # Limiter le nombre d'élèves traités
            echeanciers_retard = echeanciers_retard[:limite]
            
            rappels_crees = 0
            rappels_ignores = 0
            erreurs = 0
            
            # Créer un utilisateur système pour les rappels automatiques
            user_system, created = User.objects.get_or_create(
                username='system_rappels',
                defaults={
                    'first_name': 'Système',
                    'last_name': 'Rappels',
                    'email': 'system@ecole.com',
                    'is_active': False
                }
            )
            
            for echeancier in echeanciers_retard:
                eleve = echeancier.eleve
                
                try:
                    # Vérifier si un rappel récent existe (sauf si --force)
                    if not force:
                        dernier_rappel = Relance.objects.filter(
                            eleve=eleve,
                            date_creation__gte=timezone.now() - timezone.timedelta(days=7)
                        ).first()
                        
                        if dernier_rappel:
                            self.stdout.write(f'⏭️ {eleve.nom_complet}: rappel récent ignoré')
                            rappels_ignores += 1
                            continue
                    
                    if not dry_run:
                        # Créer le rappel
                        relance = gestionnaire_rappels.creer_rappel(
                            eleve=eleve,
                            canal=canal,
                            utilisateur=user_system
                        )
                        
                        if relance:
                            rappels_crees += 1
                            self.stdout.write(
                                f'✅ {eleve.nom_complet}: rappel créé (solde: {echeancier.solde_restant:,.0f} GNF)'
                            )
                        else:
                            erreurs += 1
                            self.stdout.write(
                                self.style.ERROR(f'❌ {eleve.nom_complet}: échec de création')
                            )
                    else:
                        # Mode simulation
                        niveau_rappel = gestionnaire_rappels.calculer_niveau_rappel(eleve.id)
                        jours_retard = gestionnaire_rappels.calculer_jours_retard(echeancier)
                        
                        self.stdout.write(
                            f'🔍 {eleve.nom_complet}: {niveau_rappel}, '
                            f'{jours_retard} jours de retard, '
                            f'{echeancier.solde_restant:,.0f} GNF'
                        )
                        rappels_crees += 1
                
                except Exception as e:
                    erreurs += 1
                    self.stdout.write(
                        self.style.ERROR(f'❌ Erreur pour {eleve.nom_complet}: {e}')
                    )
            
            # Résumé final
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('📊 RÉSUMÉ'))
            self.stdout.write('='*60)
            self.stdout.write(f'Élèves en retard détectés: {total_eleves_retard}')
            self.stdout.write(f'Rappels créés: {rappels_crees}')
            self.stdout.write(f'Rappels ignorés (récents): {rappels_ignores}')
            self.stdout.write(f'Erreurs: {erreurs}')
            
            if not dry_run and rappels_crees > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ {rappels_crees} rappels créés avec succès!')
                )
                self.stdout.write(
                    '💡 Les rappels sont maintenant disponibles dans l\'interface d\'administration'
                )
            elif dry_run:
                self.stdout.write(
                    self.style.WARNING('⚠️ Mode simulation terminé - Aucun rappel créé')
                )
            
            # Statistiques générales
            stats = gestionnaire_rappels.obtenir_statistiques_rappels()
            self.stdout.write(f'\n📈 Statistiques générales (30 derniers jours):')
            self.stdout.write(f'   Total rappels: {stats["total_rappels"]}')
            self.stdout.write(f'   Rappels envoyés: {stats["rappels_envoyes"]}')
            self.stdout.write(f'   Montant total impayé: {stats["montant_total_impaye"]:,.0f} GNF')
            
        except Exception as e:
            raise CommandError(f'Erreur lors de l\'envoi des rappels: {e}')
    
    def get_version(self):
        return '1.0.0'
