from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
from paiements.models import RemiseReduction


class Command(BaseCommand):
    help = 'Crée des remises de base pour le système'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Création des remises de base...'))
        
        # Date de début et fin pour l'année scolaire courante
        today = date.today()
        if today.month >= 9:  # Année scolaire commence en septembre
            debut_annee = date(today.year, 9, 1)
            fin_annee = date(today.year + 1, 8, 31)
        else:
            debut_annee = date(today.year - 1, 9, 1)
            fin_annee = date(today.year, 8, 31)
        
        remises_a_creer = [
            {
                'nom': 'Réduction fratrie - 2ème enfant',
                'type_remise': 'POURCENTAGE',
                'valeur': Decimal('10.00'),
                'motif': 'FRATRIE',
                'description': 'Réduction de 10% pour le deuxième enfant de la même famille',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Réduction fratrie - 3ème enfant et plus',
                'type_remise': 'POURCENTAGE',
                'valeur': Decimal('15.00'),
                'motif': 'FRATRIE',
                'description': 'Réduction de 15% à partir du troisième enfant de la même famille',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Réduction mérite scolaire',
                'type_remise': 'POURCENTAGE',
                'valeur': Decimal('20.00'),
                'motif': 'MERITE',
                'description': 'Réduction de 20% pour les élèves ayant obtenu une mention très bien',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Aide sociale',
                'type_remise': 'MONTANT_FIXE',
                'valeur': Decimal('50000'),
                'motif': 'SOCIALE',
                'description': 'Aide sociale de 50 000 GNF pour les familles en difficulté',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Enfant d\'employé',
                'type_remise': 'POURCENTAGE',
                'valeur': Decimal('25.00'),
                'motif': 'EMPLOYEE',
                'description': 'Réduction de 25% pour les enfants du personnel de l\'école',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Paiement anticipé',
                'type_remise': 'POURCENTAGE',
                'valeur': Decimal('5.00'),
                'motif': 'AUTRE',
                'description': 'Réduction de 5% pour les paiements effectués avant la date d\'échéance',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': True
            },
            {
                'nom': 'Remise exceptionnelle COVID',
                'type_remise': 'MONTANT_FIXE',
                'valeur': Decimal('30000'),
                'motif': 'AUTRE',
                'description': 'Remise exceptionnelle de 30 000 GNF liée à la situation sanitaire',
                'date_debut': debut_annee,
                'date_fin': fin_annee,
                'actif': False  # Désactivée par défaut
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for remise_data in remises_a_creer:
            remise, created = RemiseReduction.objects.get_or_create(
                nom=remise_data['nom'],
                defaults=remise_data
            )
            
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Remise créée: {remise.nom}')
                )
            else:
                # Mettre à jour les champs si la remise existe déjà
                for field, value in remise_data.items():
                    if field != 'nom':  # Ne pas modifier le nom
                        setattr(remise, field, value)
                remise.save()
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(f'↻ Remise mise à jour: {remise.nom}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Terminé! {created_count} remises créées, {updated_count} mises à jour.'
            )
        )
        
        # Afficher un résumé des remises actives
        remises_actives = RemiseReduction.objects.filter(actif=True).count()
        self.stdout.write(
            self.style.SUCCESS(f'📊 Total des remises actives: {remises_actives}')
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'🗓️  Période de validité: {debut_annee.strftime("%d/%m/%Y")} - {fin_annee.strftime("%d/%m/%Y")}'
            )
        )
