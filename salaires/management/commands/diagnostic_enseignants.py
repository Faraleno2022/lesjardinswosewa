"""
Commande pour diagnostiquer l'état des enseignants dans la base de données
Usage: python manage.py diagnostic_enseignants
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from salaires.models import Enseignant, TypeEnseignant, AffectationClasse, EtatSalaire
from eleves.models import Ecole, Classe
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Diagnostic complet de l\'état des enseignants dans la base de données'

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔍 DIAGNOSTIC DES ENSEIGNANTS - École Moderne')
        )
        self.stdout.write('=' * 60)
        
        # 1. État général de la base de données
        self.diagnostic_general()
        
        # 2. Analyse des enseignants
        self.diagnostic_enseignants()
        
        # 3. Types d'enseignants
        self.diagnostic_types()
        
        # 4. Affectations
        self.diagnostic_affectations()
        
        # 5. États de salaire
        self.diagnostic_salaires()
        
        # 6. Recommandations
        self.recommandations()

    def diagnostic_general(self):
        """Diagnostic général de la base de données"""
        self.stdout.write('\n📊 ÉTAT GÉNÉRAL:')
        self.stdout.write('-' * 30)
        
        # Écoles
        nb_ecoles = Ecole.objects.count()
        self.stdout.write(f'  • Écoles: {nb_ecoles}')
        if nb_ecoles > 0:
            ecole = Ecole.objects.first()
            self.stdout.write(f'    └─ Première école: {ecole.nom}')
        
        # Classes
        nb_classes = Classe.objects.count()
        self.stdout.write(f'  • Classes: {nb_classes}')
        
        # Utilisateurs
        nb_users = User.objects.count()
        nb_active_users = User.objects.filter(is_active=True).count()
        self.stdout.write(f'  • Utilisateurs: {nb_users} (actifs: {nb_active_users})')

    def diagnostic_enseignants(self):
        """Diagnostic des enseignants"""
        self.stdout.write('\n👨‍🏫 ENSEIGNANTS:')
        self.stdout.write('-' * 30)
        
        total_enseignants = Enseignant.objects.count()
        self.stdout.write(f'  • Total: {total_enseignants}')
        
        if total_enseignants == 0:
            self.stdout.write(
                self.style.WARNING('  ⚠️  AUCUN ENSEIGNANT TROUVÉ!')
            )
            self.stdout.write('  💡 Utilisez: python manage.py creer_enseignants_test')
            return
        
        # Répartition par statut
        actifs = Enseignant.objects.filter(statut='ACTIF').count()
        suspendus = Enseignant.objects.filter(statut='SUSPENDU').count()
        conges = Enseignant.objects.filter(statut='CONGE').count()
        
        self.stdout.write(f'  • Actifs: {actifs}')
        self.stdout.write(f'  • Suspendus: {suspendus}')
        self.stdout.write(f'  • En congé: {conges}')
        
        # Répartition par école
        ecoles_enseignants = {}
        for enseignant in Enseignant.objects.select_related('ecole'):
            ecole_nom = enseignant.ecole.nom if enseignant.ecole else 'Sans école'
            ecoles_enseignants[ecole_nom] = ecoles_enseignants.get(ecole_nom, 0) + 1
        
        self.stdout.write('  • Par école:')
        for ecole, count in ecoles_enseignants.items():
            self.stdout.write(f'    └─ {ecole}: {count}')
        
        # Liste des premiers enseignants
        self.stdout.write('  • Premiers enseignants:')
        for enseignant in Enseignant.objects.all()[:5]:
            self.stdout.write(
                f'    └─ ID {enseignant.id}: {enseignant.nom} {enseignant.prenoms} '
                f'({enseignant.type_enseignant}, {enseignant.statut})'
            )

    def diagnostic_types(self):
        """Diagnostic des types d'enseignants"""
        self.stdout.write('\n📋 TYPES D\'ENSEIGNANTS:')
        self.stdout.write('-' * 30)
        
        # Types définis dans le modèle comme TextChoices
        self.stdout.write('  • Types disponibles:')
        for code, libelle in TypeEnseignant.choices:
            count = Enseignant.objects.filter(type_enseignant=code).count()
            self.stdout.write(f'    └─ {code} ({libelle}): {count} enseignants')
        
        # Note: TypeEnseignant est un TextChoices, pas un modèle de base de données
        self.stdout.write('  • Types: Définis comme TextChoices dans le modèle')

    def diagnostic_affectations(self):
        """Diagnostic des affectations"""
        self.stdout.write('\n🏫 AFFECTATIONS:')
        self.stdout.write('-' * 30)
        
        try:
            total_affectations = AffectationClasse.objects.count()
            affectations_actives = AffectationClasse.objects.filter(actif=True).count()
            
            self.stdout.write(f'  • Total: {total_affectations}')
            self.stdout.write(f'  • Actives: {affectations_actives}')
            
            # Affectations par enseignant
            if total_affectations > 0:
                self.stdout.write('  • Répartition:')
                enseignants_avec_affectations = (
                    Enseignant.objects
                    .prefetch_related('affectations')
                    .annotate(nb_affectations=Count('affectations'))
                    .filter(nb_affectations__gt=0)[:5]
                )
                for enseignant in enseignants_avec_affectations:
                    self.stdout.write(
                        f'    └─ {enseignant.nom}: {enseignant.nb_affectations} affectations'
                    )
        except:
            self.stdout.write('  • Affectations: Module non configuré')

    def diagnostic_salaires(self):
        """Diagnostic des états de salaire"""
        self.stdout.write('\n💰 ÉTATS DE SALAIRE:')
        self.stdout.write('-' * 30)
        
        try:
            total_etats = EtatSalaire.objects.count()
            etats_valides = EtatSalaire.objects.filter(valide=True).count()
            
            self.stdout.write(f'  • Total: {total_etats}')
            self.stdout.write(f'  • Validés: {etats_valides}')
            
            if total_etats > 0:
                # Derniers états
                derniers_etats = (
                    EtatSalaire.objects
                    .select_related('enseignant', 'periode')
                    .order_by('-periode__annee', '-periode__mois')[:3]
                )
                self.stdout.write('  • Derniers états:')
                for etat in derniers_etats:
                    self.stdout.write(
                        f'    └─ {etat.enseignant.nom} - '
                        f'{etat.periode.mois}/{etat.periode.annee}: '
                        f'{etat.salaire_net:,.0f} GNF'
                    )
        except:
            self.stdout.write('  • États de salaire: Module non configuré')

    def recommandations(self):
        """Recommandations basées sur le diagnostic"""
        self.stdout.write('\n💡 RECOMMANDATIONS:')
        self.stdout.write('-' * 30)
        
        total_enseignants = Enseignant.objects.count()
        
        if total_enseignants == 0:
            self.stdout.write(
                self.style.WARNING('  🔴 CRITIQUE: Aucun enseignant dans la base!')
            )
            self.stdout.write('     └─ Exécuter: python manage.py creer_enseignants_test')
            self.stdout.write('     └─ Ou ajouter manuellement via /salaires/enseignants/ajouter/')
        
        elif total_enseignants < 3:
            self.stdout.write(
                self.style.WARNING('  🟡 ATTENTION: Très peu d\'enseignants!')
            )
            self.stdout.write('     └─ Considérer ajouter plus de données de test')
        
        else:
            self.stdout.write(
                self.style.SUCCESS('  ✅ Base de données enseignants semble correcte')
            )
        
        # Vérifications spécifiques
        nb_ecoles = Ecole.objects.count()
        if nb_ecoles == 0:
            self.stdout.write('  🔴 Aucune école: Créer une école d\'abord')
        
        nb_classes = Classe.objects.count()
        if nb_classes == 0:
            self.stdout.write('  🟡 Aucune classe: Considérer créer des classes')
        
        # URLs de test recommandées
        if total_enseignants > 0:
            premier_enseignant = Enseignant.objects.first()
            self.stdout.write('\n🔗 URLS DE TEST:')
            self.stdout.write(f'  • Liste: /salaires/enseignants/')
            self.stdout.write(f'  • Détail: /salaires/enseignants/{premier_enseignant.id}/')
            self.stdout.write(f'  • Tableau de bord: /salaires/')
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(
            self.style.SUCCESS('✅ Diagnostic terminé!')
        )
