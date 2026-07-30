from django.core.management.base import BaseCommand
from paiements.models import TypePaiement


class Command(BaseCommand):
    help = 'Créer les nouveaux types de paiement combinés'

    def handle(self, *args, **options):
        # Types de paiement combinés à créer
        types_combines = [
            {
                'nom': 'Frais d\'inscription + 1ère tranche',
                'description': 'Paiement combiné des frais d\'inscription (30 000 GNF) et de la première tranche de scolarité'
            },
            {
                'nom': 'Frais d\'inscription + 1ère tranche + 2ème tranche',
                'description': 'Paiement combiné des frais d\'inscription et des deux premières tranches de scolarité'
            },
            {
                'nom': 'Frais d\'inscription + Annuel',
                'description': 'Paiement combiné des frais d\'inscription et du montant annuel complet de scolarité'
            }
        ]

        created_count = 0
        
        for type_data in types_combines:
            type_paiement, created = TypePaiement.objects.get_or_create(
                nom=type_data['nom'],
                defaults={
                    'description': type_data['description'],
                    'actif': True
                }
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Créé: {type_paiement.nom}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'• Existe déjà: {type_paiement.nom}')
                )

        self.stdout.write(
            self.style.SUCCESS(f'\n{created_count} nouveaux types de paiement combinés créés.')
        )
