from django.core.management.base import BaseCommand
from notes.models import ClasseNote, MatiereNote
from eleves.models import Ecole
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Génère les matières par défaut pour toutes les classes (Primaire et Secondaire)'

    def handle(self, *args, **options):
        # Récupérer l'école par défaut (à adapter selon votre configuration)
        ecole = Ecole.objects.first()
        if not ecole:
            self.stdout.write(self.style.ERROR("Aucune école trouvée. Veuillez d'abord créer une école."))
            return

        # Récupérer l'utilisateur admin
        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write(self.style.ERROR("Aucun utilisateur administrateur trouvé."))
            return

        # Définition des matières par niveau
        matieres_par_niveau = {
            # PRIMAIRE (1ère à 6ème année) - SANS COEFFICIENT
            'PRIMAIRE_1': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            'PRIMAIRE_2': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            'PRIMAIRE_3': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            'PRIMAIRE_4': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            'PRIMAIRE_5': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            'PRIMAIRE_6': [
                {'nom': 'Lecture', 'code': 'LEC', 'coef': None},
                {'nom': 'Dictée et questions', 'code': 'DIC', 'coef': None},
                {'nom': 'Écriture', 'code': 'ECR', 'coef': None},
                {'nom': 'Rédaction', 'code': 'RED', 'coef': None},
                {'nom': 'Sciences d\'observation', 'code': 'SCI', 'coef': None},
                {'nom': 'Histoire', 'code': 'HIS', 'coef': None},
                {'nom': 'Dessin', 'code': 'DES', 'coef': None},
                {'nom': 'Géographie', 'code': 'GEO', 'coef': None},
                {'nom': 'Morale', 'code': 'MOR', 'coef': None},
                {'nom': 'Calcul', 'code': 'CAL', 'coef': None},
                {'nom': 'Récitation', 'code': 'REC', 'coef': None},
                {'nom': 'Chant', 'code': 'CHA', 'coef': None},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': None},
            ],
            
            # SECONDAIRE (11ème à Terminale)
            'LYCEE_11': [
                {'nom': 'Français', 'code': 'FR', 'coef': 3},
                {'nom': 'Mathématiques', 'code': 'MATH', 'coef': 4},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': 2},
                {'nom': 'Physique-Chimie', 'code': 'PC', 'coef': 4},
                {'nom': 'Sciences de la Vie et de la Terre', 'code': 'SVT', 'coef': 3},
                {'nom': 'Histoire-Géographie', 'code': 'HG', 'coef': 2},
                {'nom': 'Philosophie', 'code': 'PHILO', 'coef': 2},
                {'nom': 'Éducation Civique', 'code': 'EC', 'coef': 1},
                {'nom': 'Éducation Physique et Sportive', 'code': 'EPS', 'coef': 1},
                {'nom': 'Sciences Économiques et Sociales', 'code': 'SES', 'coef': 2},
            ],
            'LYCEE_12': [
                {'nom': 'Français', 'code': 'FR', 'coef': 3},
                {'nom': 'Mathématiques', 'code': 'MATH', 'coef': 4},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': 2},
                {'nom': 'Physique-Chimie', 'code': 'PC', 'coef': 4},
                {'nom': 'Sciences de la Vie et de la Terre', 'code': 'SVT', 'coef': 3},
                {'nom': 'Histoire-Géographie', 'code': 'HG', 'coef': 2},
                {'nom': 'Philosophie', 'code': 'PHILO', 'coef': 2},
                {'nom': 'Éducation Civique', 'code': 'EC', 'coef': 1},
                {'nom': 'Éducation Physique et Sportive', 'code': 'EPS', 'coef': 1},
                {'nom': 'Sciences Économiques et Sociales', 'code': 'SES', 'coef': 2},
            ],
            'TERMINALE': [
                {'nom': 'Français', 'code': 'FR', 'coef': 3},
                {'nom': 'Mathématiques', 'code': 'MATH', 'coef': 4},
                {'nom': 'Anglais', 'code': 'ANG', 'coef': 2},
                {'nom': 'Physique-Chimie', 'code': 'PC', 'coef': 4},
                {'nom': 'Sciences de la Vie et de la Terre', 'code': 'SVT', 'coef': 3},
                {'nom': 'Histoire-Géographie', 'code': 'HG', 'coef': 2},
                {'nom': 'Philosophie', 'code': 'PHILO', 'coef': 2},
                {'nom': 'Économie', 'code': 'ECO', 'coef': 2},
                {'nom': 'Éducation Civique', 'code': 'EC', 'coef': 1},
                {'nom': 'Éducation Physique et Sportive', 'code': 'EPS', 'coef': 1},
            ],
        }

        # Parcourir toutes les classes existantes
        classes = ClasseNote.objects.filter(ecole=ecole)
        if not classes.exists():
            self.stdout.write(self.style.ERROR(f"Aucune classe trouvée pour l'école {ecole.nom}."))
            return

        total_matieres_crees = 0
        total_matieres_existantes = 0

        for classe in classes:
            niveau = classe.niveau
            if niveau not in matieres_par_niveau:
                self.stdout.write(self.style.WARNING(
                    f"Aucune matière définie pour le niveau {niveau}. Passage à la classe suivante..."
                ))
                continue

            self.stdout.write(f"\n📚 Traitement de la classe : {classe.nom} ({classe.get_niveau_display()})")
            self.stdout.write("-" * 70)

            matieres = matieres_par_niveau[niveau]
            for matiere_data in matieres:
                # Vérifier si la matière existe déjà pour cette classe
                matiere_existante = MatiereNote.objects.filter(
                    classe=classe,
                    code=matiere_data['code']
                ).first()

                if not matiere_existante:
                    MatiereNote.objects.create(
                        classe=classe,
                        nom=matiere_data['nom'],
                        code=matiere_data['code'],
                        coefficient=matiere_data['coef'],
                        cree_par=admin
                    )
                    total_matieres_crees += 1
                    
                    # Affichage avec ou sans coefficient selon le niveau
                    if matiere_data['coef'] is None:
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✓ {matiere_data['nom']:<40}"
                        ))
                    else:
                        self.stdout.write(self.style.SUCCESS(
                            f"  ✓ {matiere_data['nom']:<40} (Coef: {matiere_data['coef']})"
                        ))
                else:
                    total_matieres_existantes += 1
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠ {matiere_data['nom']:<40} (Existe déjà)"
                    ))

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS(
            f"✅ Opération terminée !\n"
            f"   • Matières créées : {total_matieres_crees}\n"
            f"   • Matières existantes : {total_matieres_existantes}"
        ))
