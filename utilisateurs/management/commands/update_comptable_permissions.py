"""
Commande Django pour mettre à jour les permissions des comptables existants
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from utilisateurs.models import Profil


class Command(BaseCommand):
    help = 'Met à jour les permissions granulaires des comptables existants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--restrict-all',
            action='store_true',
            help='Restreindre tous les comptables (ne peuvent pas ajouter paiements, dépenses, enseignants)',
        )
        parser.add_argument(
            '--allow-all',
            action='store_true',
            help='Autoriser tous les comptables (peuvent tout faire)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Afficher les changements sans les appliquer',
        )

    def handle(self, *args, **options):
        comptables = Profil.objects.filter(role='COMPTABLE')
        
        if not comptables.exists():
            self.stdout.write(
                self.style.WARNING('Aucun comptable trouvé dans la base de données.')
            )
            return

        self.stdout.write(f'Trouvé {comptables.count()} comptable(s) à mettre à jour.')

        if options['restrict_all']:
            self.update_permissions(comptables, restrict=True, dry_run=options['dry_run'])
        elif options['allow_all']:
            self.update_permissions(comptables, restrict=False, dry_run=options['dry_run'])
        else:
            # Configuration par défaut : restreindre les ajouts, permettre les modifications
            self.update_permissions(comptables, restrict=True, dry_run=options['dry_run'], default=True)

    def update_permissions(self, comptables, restrict=True, dry_run=False, default=False):
        """Met à jour les permissions des comptables"""
        
        if default:
            # Configuration par défaut sécurisée
            permissions = {
                'peut_ajouter_paiements': False,
                'peut_ajouter_depenses': False,
                'peut_ajouter_enseignants': False,
                'peut_modifier_paiements': True,
                'peut_modifier_depenses': True,
                'peut_supprimer_paiements': False,
                'peut_supprimer_depenses': False,
                'peut_consulter_rapports': True,
            }
            action_desc = "Configuration par défaut (sécurisée)"
        elif restrict:
            # Tout restreindre
            permissions = {
                'peut_ajouter_paiements': False,
                'peut_ajouter_depenses': False,
                'peut_ajouter_enseignants': False,
                'peut_modifier_paiements': False,
                'peut_modifier_depenses': False,
                'peut_supprimer_paiements': False,
                'peut_supprimer_depenses': False,
                'peut_consulter_rapports': True,
            }
            action_desc = "Restriction complète"
        else:
            # Tout autoriser
            permissions = {
                'peut_ajouter_paiements': True,
                'peut_ajouter_depenses': True,
                'peut_ajouter_enseignants': True,
                'peut_modifier_paiements': True,
                'peut_modifier_depenses': True,
                'peut_supprimer_paiements': True,
                'peut_supprimer_depenses': True,
                'peut_consulter_rapports': True,
            }
            action_desc = "Autorisation complète"

        self.stdout.write(f'\n{action_desc} appliquée :')
        for perm, value in permissions.items():
            status = "✅ Autorisé" if value else "❌ Restreint"
            self.stdout.write(f'  - {perm}: {status}')

        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n🔍 MODE DRY-RUN : Aucun changement appliqué')
            )
            return

        try:
            with transaction.atomic():
                updated_count = 0
                for comptable in comptables:
                    # Vérifier si les champs existent (pour éviter les erreurs de migration)
                    try:
                        for perm, value in permissions.items():
                            if hasattr(comptable, perm):
                                setattr(comptable, perm, value)
                        comptable.save()
                        updated_count += 1
                        
                        self.stdout.write(
                            f'✅ {comptable.user.get_full_name() or comptable.user.username} - Mis à jour'
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f'❌ Erreur pour {comptable.user.username}: {str(e)}'
                            )
                        )

                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n🎉 {updated_count}/{comptables.count()} comptable(s) mis à jour avec succès !'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Erreur lors de la mise à jour : {str(e)}')
            )

    def show_current_permissions(self, comptables):
        """Affiche les permissions actuelles des comptables"""
        self.stdout.write('\n📋 Permissions actuelles des comptables :')
        
        for comptable in comptables:
            self.stdout.write(f'\n👤 {comptable.user.get_full_name() or comptable.user.username}:')
            
            permissions = [
                ('peut_ajouter_paiements', 'Ajouter paiements'),
                ('peut_ajouter_depenses', 'Ajouter dépenses'),
                ('peut_ajouter_enseignants', 'Ajouter enseignants'),
                ('peut_modifier_paiements', 'Modifier paiements'),
                ('peut_modifier_depenses', 'Modifier dépenses'),
                ('peut_supprimer_paiements', 'Supprimer paiements'),
                ('peut_supprimer_depenses', 'Supprimer dépenses'),
                ('peut_consulter_rapports', 'Consulter rapports'),
            ]
            
            for perm_field, perm_name in permissions:
                if hasattr(comptable, perm_field):
                    value = getattr(comptable, perm_field)
                    status = "✅" if value else "❌"
                    self.stdout.write(f'  {status} {perm_name}')
                else:
                    self.stdout.write(f'  ⚠️  {perm_name} (champ non trouvé)')
