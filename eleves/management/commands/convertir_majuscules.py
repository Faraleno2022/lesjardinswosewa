"""
Commande de gestion Django pour convertir toutes les données texte existantes en majuscules.
Usage: python manage.py convertir_majuscules
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from eleves.models import Eleve, Responsable, Classe, Ecole


class Command(BaseCommand):
    help = 'Convertit toutes les données texte existantes en majuscules (élèves, responsables, classes, écoles)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les modifications sans les appliquer',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN: Aucune modification ne sera appliquée'))
        
        stats = {
            'eleves': 0,
            'responsables': 0,
            'classes': 0,
            'ecoles': 0,
        }
        
        try:
            with transaction.atomic():
                # 1. Convertir les élèves
                self.stdout.write('\n📚 Conversion des élèves...')
                eleves = Eleve.objects.all()
                for eleve in eleves:
                    modified = False
                    
                    if eleve.nom and eleve.nom != eleve.nom.upper():
                        self.stdout.write(f'  - Élève: {eleve.nom} → {eleve.nom.upper()}')
                        eleve.nom = eleve.nom.upper()
                        modified = True
                    
                    if eleve.prenom and eleve.prenom != eleve.prenom.upper():
                        self.stdout.write(f'  - Prénom: {eleve.prenom} → {eleve.prenom.upper()}')
                        eleve.prenom = eleve.prenom.upper()
                        modified = True
                    
                    if eleve.lieu_naissance and eleve.lieu_naissance != eleve.lieu_naissance.upper():
                        self.stdout.write(f'  - Lieu: {eleve.lieu_naissance} → {eleve.lieu_naissance.upper()}')
                        eleve.lieu_naissance = eleve.lieu_naissance.upper()
                        modified = True
                    
                    if modified:
                        if not dry_run:
                            eleve.save()
                        stats['eleves'] += 1
                
                # 2. Convertir les responsables
                self.stdout.write('\n👨‍👩‍👧 Conversion des responsables...')
                responsables = Responsable.objects.all()
                for resp in responsables:
                    modified = False
                    
                    if resp.nom and resp.nom != resp.nom.upper():
                        self.stdout.write(f'  - Responsable: {resp.nom} → {resp.nom.upper()}')
                        resp.nom = resp.nom.upper()
                        modified = True
                    
                    if resp.prenom and resp.prenom != resp.prenom.upper():
                        self.stdout.write(f'  - Prénom: {resp.prenom} → {resp.prenom.upper()}')
                        resp.prenom = resp.prenom.upper()
                        modified = True
                    
                    if resp.adresse and resp.adresse != resp.adresse.upper():
                        resp.adresse = resp.adresse.upper()
                        modified = True
                    
                    if resp.profession and resp.profession != resp.profession.upper():
                        resp.profession = resp.profession.upper()
                        modified = True
                    
                    if modified:
                        if not dry_run:
                            resp.save()
                        stats['responsables'] += 1
                
                # 3. Convertir les classes
                self.stdout.write('\n🏫 Conversion des classes...')
                classes = Classe.objects.all()
                for classe in classes:
                    if classe.nom and classe.nom != classe.nom.upper():
                        self.stdout.write(f'  - Classe: {classe.nom} → {classe.nom.upper()}')
                        classe.nom = classe.nom.upper()
                        if not dry_run:
                            classe.save()
                        stats['classes'] += 1
                
                # 4. Convertir les écoles
                self.stdout.write('\n🏢 Conversion des écoles...')
                ecoles = Ecole.objects.all()
                for ecole in ecoles:
                    modified = False
                    
                    if ecole.nom and ecole.nom != ecole.nom.upper():
                        self.stdout.write(f'  - École: {ecole.nom} → {ecole.nom.upper()}')
                        ecole.nom = ecole.nom.upper()
                        modified = True
                    
                    if ecole.adresse and ecole.adresse != ecole.adresse.upper():
                        ecole.adresse = ecole.adresse.upper()
                        modified = True
                    
                    if ecole.directeur and ecole.directeur != ecole.directeur.upper():
                        self.stdout.write(f'  - Directeur: {ecole.directeur} → {ecole.directeur.upper()}')
                        ecole.directeur = ecole.directeur.upper()
                        modified = True
                    
                    if ecole.ire and ecole.ire != ecole.ire.upper():
                        ecole.ire = ecole.ire.upper()
                        modified = True
                    
                    if ecole.dpe and ecole.dpe != ecole.dpe.upper():
                        ecole.dpe = ecole.dpe.upper()
                        modified = True
                    
                    if ecole.desee and ecole.desee != ecole.desee.upper():
                        ecole.desee = ecole.desee.upper()
                        modified = True
                    
                    if modified:
                        if not dry_run:
                            ecole.save()
                        stats['ecoles'] += 1
                
                # Si dry-run, annuler la transaction
                if dry_run:
                    transaction.set_rollback(True)
        
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Erreur: {str(e)}'))
            return
        
        # Afficher les statistiques
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✅ Conversion terminée avec succès!\n'))
        self.stdout.write(f'📊 Statistiques:')
        self.stdout.write(f'  - Élèves modifiés: {stats["eleves"]}')
        self.stdout.write(f'  - Responsables modifiés: {stats["responsables"]}')
        self.stdout.write(f'  - Classes modifiées: {stats["classes"]}')
        self.stdout.write(f'  - Écoles modifiées: {stats["ecoles"]}')
        self.stdout.write(f'  - TOTAL: {sum(stats.values())} enregistrements')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\n⚠️  Mode DRY-RUN: Aucune modification n\'a été appliquée'))
            self.stdout.write('Pour appliquer les modifications, exécutez:')
            self.stdout.write(self.style.SUCCESS('python manage.py convertir_majuscules'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Toutes les modifications ont été enregistrées en base de données'))
