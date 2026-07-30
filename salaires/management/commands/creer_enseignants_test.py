"""
Commande pour créer des enseignants de test
Usage: python manage.py creer_enseignants_test
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from salaires.models import Enseignant, TypeEnseignant
from eleves.models import Ecole
from decimal import Decimal

class Command(BaseCommand):
    help = 'Crée des enseignants de test pour le développement'

    def add_arguments(self, parser):
        parser.add_argument(
            '--nombre',
            type=int,
            default=5,
            help='Nombre d\'enseignants à créer (défaut: 5)',
        )

    def handle(self, *args, **options):
        nombre = options['nombre']
        
        # Récupérer une école existante
        ecole = Ecole.objects.first()
        if not ecole:
            self.stdout.write(
                self.style.ERROR('Aucune école trouvée. Créez d\'abord une école.')
            )
            return
        
        # Les types d'enseignants sont définis dans le modèle comme TextChoices
        # Pas besoin de les créer en base de données
        self.stdout.write('  • Types d\'enseignants disponibles:')
        for code, libelle in TypeEnseignant.choices:
            self.stdout.write(f'    └─ {code}: {libelle}')
        
        # Données de test pour les enseignants
        enseignants_data = [
            {
                'nom': 'DIALLO',
                'prenoms': 'Mamadou',
                'email': 'mamadou.diallo@ecole.gn',
                'telephone': '622123456',
                'type_enseignant': 'PRIMAIRE',
                'salaire_fixe': Decimal('800000'),
                'statut': 'ACTIF'
            },
            {
                'nom': 'BARRY',
                'prenoms': 'Fatoumata',
                'email': 'fatoumata.barry@ecole.gn',
                'telephone': '622234567',
                'type_enseignant': 'SECONDAIRE',
                'taux_horaire': Decimal('15000'),
                'statut': 'ACTIF'
            },
            {
                'nom': 'CAMARA',
                'prenoms': 'Ibrahima',
                'email': 'ibrahima.camara@ecole.gn',
                'telephone': '622345678',
                'type_enseignant': 'ADMINISTRATEUR',
                'salaire_fixe': Decimal('1500000'),
                'statut': 'ACTIF'
            },
            {
                'nom': 'SOW',
                'prenoms': 'Aissatou',
                'email': 'aissatou.sow@ecole.gn',
                'telephone': '622456789',
                'type_enseignant': 'PRIMAIRE',
                'salaire_fixe': Decimal('750000'),
                'statut': 'ACTIF'
            },
            {
                'nom': 'TOURE',
                'prenoms': 'Mohamed',
                'email': 'mohamed.toure@ecole.gn',
                'telephone': '622567890',
                'type_enseignant': 'ADMINISTRATEUR',
                'salaire_fixe': Decimal('600000'),
                'statut': 'SUSPENDU'
            }
        ]
        
        created_count = 0
        for i in range(min(nombre, len(enseignants_data))):
            data = enseignants_data[i]
            
            # Vérifier si l'enseignant existe déjà
            if not Enseignant.objects.filter(email=data['email']).exists():
                enseignant = Enseignant.objects.create(
                    ecole=ecole,
                    nom=data['nom'],
                    prenoms=data['prenoms'],
                    email=data['email'],
                    telephone=data['telephone'],
                    type_enseignant=data['type_enseignant'],
                    salaire_base=data['salaire_base'],
                    statut=data['statut'],
                    date_embauche=timezone.now().date()
                )
                created_count += 1
                self.stdout.write(
                    f'  ✓ Enseignant créé: {enseignant.nom} {enseignant.prenoms} (ID: {enseignant.id})'
                )
            else:
                self.stdout.write(
                    f'  - Enseignant existe déjà: {data["nom"]} {data["prenoms"]}'
                )
        
        # Créer des enseignants supplémentaires si demandé
        if nombre > len(enseignants_data):
            for i in range(len(enseignants_data), nombre):
                enseignant = Enseignant.objects.create(
                    ecole=ecole,
                    nom=f'ENSEIGNANT{i+1}',
                    prenoms=f'Test{i+1}',
                    email=f'test{i+1}@ecole.gn',
                    telephone=f'62200000{i+1:02d}',
                    type_enseignant='PRIMAIRE',
                    salaire_fixe=Decimal('700000'),
                    statut='ACTIF',
                    date_embauche=timezone.now().date()
                )
                created_count += 1
                self.stdout.write(
                    f'  ✓ Enseignant créé: {enseignant.nom} {enseignant.prenoms} (ID: {enseignant.id})'
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {created_count} enseignants créés avec succès!')
        )
        
        # Afficher le premier enseignant pour test
        premier_enseignant = Enseignant.objects.first()
        if premier_enseignant:
            self.stdout.write(
                self.style.SUCCESS(
                    f'🔗 Testez avec: /salaires/enseignants/{premier_enseignant.id}/'
                )
            )
