from django.core.management.base import BaseCommand
from notes.models import ClasseNote, MatiereNote
from notes.matieres_defaut import MATIERES_MATERNELLE
from eleves.models import Ecole
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Met à jour les matières par défaut pour les classes de maternelle avec la nouvelle liste'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Forcer la recréation de toutes les matières (supprime les existantes)',
        )
        parser.add_argument(
            '--classe-id',
            type=int,
            help='Appliquer uniquement à une classe spécifique (ID)',
        )

    def handle(self, *args, **options):
        # Récupérer l'école par défaut
        ecole = Ecole.objects.first()
        if not ecole:
            self.stdout.write(self.style.ERROR("Aucune école trouvée. Veuillez d'abord créer une école."))
            return

        # Récupérer l'utilisateur admin
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR("Aucun utilisateur administrateur trouvé."))
            return

        # Filtrer les classes de maternelle
        classes_maternelle = ClasseNote.objects.filter(
            ecole=ecole,
            niveau='MATERNELLE'
        )

        # Débogage
        self.stdout.write(f"🔍 Recherche des classes maternelle pour l'école {ecole.nom}...")
        self.stdout.write(f"   • Total classes trouvées : {classes_maternelle.count()}")
        for c in classes_maternelle:
            self.stdout.write(f"     - ID: {c.id}, Nom: {c.nom}, Niveau: '{c.niveau}'")

        if options.get('classe_id'):
            classe_id = options['classe_id']
            self.stdout.write(f"🎯 Filtre par classe ID : {classe_id}")
            classes_maternelle = classes_maternelle.filter(id=classe_id)
            self.stdout.write(f"   • Classes après filtre : {classes_maternelle.count()}")

        if not classes_maternelle.exists():
            self.stdout.write(self.style.ERROR("Aucune classe de maternelle trouvée."))
            return

        force = options.get('force', False)
        total_matieres_crees = 0
        total_matieres_existantes = 0
        total_matieres_supprimees = 0

        self.stdout.write(self.style.SUCCESS("🎨 MISE À JOUR DES MATIÈRES MATERNELLE"))
        self.stdout.write("=" * 70)

        for classe in classes_maternelle:
            self.stdout.write(f"\n📚 Classe : {classe.nom}")
            self.stdout.write("-" * 50)

            # Si force est activé, supprimer d'abord toutes les matières existantes
            if force:
                matieres_existantes = MatiereNote.objects.filter(classe=classe)
                count_supprimees = matieres_existantes.count()
                if count_supprimees > 0:
                    matieres_existantes.delete()
                    total_matieres_supprimees += count_supprimees
                    self.stdout.write(self.style.WARNING(
                        f"  🗑️  {count_supprimees} matière(s) supprimée(s)"
                    ))

            # Ajouter les nouvelles matières
            for matiere_data in MATIERES_MATERNELLE:
                # Vérifier si la matière existe déjà
                matiere_existante = MatiereNote.objects.filter(
                    classe=classe,
                    code=matiere_data['code']
                ).first()

                if not matiere_existante:
                    # Créer la nouvelle matière
                    MatiereNote.objects.create(
                        classe=classe,
                        nom=matiere_data['nom'],
                        code=matiere_data['code'],
                        coefficient=matiere_data['coefficient'],
                        actif=True,
                        cree_par=admin
                    )
                    total_matieres_crees += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"  ✅ {matiere_data['nom']:<30} ({matiere_data['code']})"
                    ))
                else:
                    total_matieres_existantes += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  {matiere_data['nom']:<30} ({matiere_data['code']}) - Déjà existante"
                    ))

        # Résumé final
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("📊 RÉSUMÉ DE L'OPÉRATION"))
        self.stdout.write(f"  • Classes traitées : {classes_maternelle.count()}")
        self.stdout.write(f"  • Matières créées : {total_matieres_crees}")
        self.stdout.write(f"  • Matières existantes : {total_matieres_existantes}")
        if force:
            self.stdout.write(f"  • Matières supprimées : {total_matieres_supprimees}")

        # Afficher la liste des matières configurées
        self.stdout.write("\n🎯 MATIÈRES MATERNELLE CONFIGURÉES :")
        for matiere in MATIERES_MATERNELLE:
            self.stdout.write(f"  • {matiere['nom']:<30} (Code: {matiere['code']})")

        self.stdout.write("\n✅ Opération terminée avec succès !")
