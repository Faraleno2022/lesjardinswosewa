"""Réaffecte les classes de maternelle au niveau détaillé correspondant à leur nom.

Les niveaux Crèche, Toute petite section, Petite section, Moyenne section et
Grande section ont été ajoutés après coup : les classes créées avant portent
encore le niveau générique « Maternelle » (ou « Garderie »). Leur grille
tarifaire n'est alors jamais trouvée — l'échéancier des élèves reste vide et
plus aucun paiement ne peut être enregistré.

Cette commande détecte ces classes d'après leur nom et corrige leur niveau.

    python manage.py corriger_niveaux_maternelle              # simulation
    python manage.py corriger_niveaux_maternelle --appliquer  # applique
"""
import unicodedata

from django.core.management.base import BaseCommand
from django.db import transaction

from eleves.models import Classe, Ecole

# Niveaux génériques à re-ventiler (on ne touche jamais au primaire/collège/lycée)
NIVEAUX_A_CORRIGER = {'MATERNELLE', 'GARDERIE'}

# Nom de classe (normalisé) -> niveau détaillé attendu.
# Les clés sont recherchées comme sous-chaînes du nom de la classe, les plus
# longues d'abord pour éviter que « petite section » ne capture « toute petite
# section ».
MAPPING_NOM_NIVEAU = {
    # Maternelle
    'toute petite section': 'TOUTE_PETITE_SECTION',
    'tres petite section': 'TOUTE_PETITE_SECTION',
    'tps': 'TOUTE_PETITE_SECTION',
    'petite section': 'PETITE_SECTION',
    'moyenne section': 'MOYENNE_SECTION',
    'moyen section': 'MOYENNE_SECTION',
    'grande section': 'GRANDE_SECTION',
    'creche': 'CRECHE',
    'garderie': 'GARDERIE',
    'ps': 'PETITE_SECTION',
    'ms': 'MOYENNE_SECTION',
    'gs': 'GRANDE_SECTION',
    # Primaire / collège : une classe de primaire ou de collège peut elle aussi
    # avoir été rattachée par erreur au niveau générique « Maternelle ».
    '1ere annee': 'PRIMAIRE_1',
    '1re annee': 'PRIMAIRE_1',
    '2eme annee': 'PRIMAIRE_2',
    '3eme annee': 'PRIMAIRE_3',
    '4eme annee': 'PRIMAIRE_4',
    '5eme annee': 'PRIMAIRE_5',
    '6eme annee': 'PRIMAIRE_6',
    '7eme annee': 'COLLEGE_7',
    '8eme annee': 'COLLEGE_8',
    '9eme annee': 'COLLEGE_9',
    '10eme annee': 'COLLEGE_10',
}


def _normaliser(valeur: str) -> str:
    """Minuscules, sans accents, espaces uniformisés."""
    texte = (valeur or '').strip().lower()
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return ' '.join(texte.split())


def deduire_niveau(nom_classe: str):
    """Retourne le niveau détaillé déduit du nom, ou None si indéterminable."""
    nom = _normaliser(nom_classe)
    if not nom:
        return None
    # Les libellés les plus longs d'abord (« toute petite section » avant « petite section »)
    for cle in sorted(MAPPING_NOM_NIVEAU, key=len, reverse=True):
        if len(cle) <= 3:
            # Abréviations (ps, ms, gs, tps) : exiger un mot entier, sinon
            # « ps » matcherait « Temps », « Reprise »...
            if cle in nom.split():
                return MAPPING_NOM_NIVEAU[cle]
        elif cle in nom:
            return MAPPING_NOM_NIVEAU[cle]
    return None


class Command(BaseCommand):
    help = (
        "Réaffecte les classes portant le niveau générique Maternelle/Garderie "
        "au niveau détaillé correspondant à leur nom (Crèche, TPS, PS, MS, GS)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Applique réellement les changements (sans ce drapeau : simulation seule).",
        )
        parser.add_argument(
            '--ecole', type=str, default=None,
            help="Limiter à une école (nom exact ou partiel).",
        )
        parser.add_argument(
            '--annee', type=str, default=None,
            help="Limiter à une année scolaire (ex: 2026-2027).",
        )

    def handle(self, *args, **options):
        appliquer = options['appliquer']
        classes = Classe.objects.filter(niveau__in=NIVEAUX_A_CORRIGER).select_related('ecole')

        if options['ecole']:
            classes = classes.filter(ecole__nom__icontains=options['ecole'])
        if options['annee']:
            classes = classes.filter(annee_scolaire=options['annee'])

        classes = classes.order_by('ecole__nom', 'annee_scolaire', 'nom')

        if not classes.exists():
            self.stdout.write(self.style.SUCCESS(
                "Aucune classe au niveau générique Maternelle/Garderie : rien à corriger."
            ))
            return

        a_corriger = []
        indetermines = []
        for classe in classes:
            nouveau = deduire_niveau(classe.nom)
            if nouveau and nouveau != classe.niveau:
                a_corriger.append((classe, nouveau))
            elif not nouveau:
                indetermines.append(classe)

        self.stdout.write("")
        if a_corriger:
            titre = "Changements à appliquer :" if appliquer else "Changements proposés (simulation) :"
            self.stdout.write(self.style.MIGRATE_HEADING(titre))
            for classe, nouveau in a_corriger:
                self.stdout.write(
                    f"  {classe.ecole.nom} | {classe.annee_scolaire} | {classe.nom} : "
                    f"{classe.get_niveau_display()} -> {dict(Classe.NIVEAUX_CHOICES)[nouveau]}"
                )
        else:
            self.stdout.write(self.style.SUCCESS("Aucun changement nécessaire."))

        if indetermines:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(
                "Classes dont le niveau n'a pas pu être déduit du nom (à corriger à la main) :"
            ))
            for classe in indetermines:
                self.stdout.write(
                    f"  {classe.ecole.nom} | {classe.annee_scolaire} | {classe.nom} "
                    f"({classe.get_niveau_display()})"
                )

        self.stdout.write("")
        if not a_corriger:
            return

        if not appliquer:
            self.stdout.write(self.style.WARNING(
                f"Simulation : {len(a_corriger)} classe(s) seraient modifiée(s). "
                "Relancez avec --appliquer pour enregistrer."
            ))
            return

        with transaction.atomic():
            for classe, nouveau in a_corriger:
                classe.niveau = nouveau
                classe.save(update_fields=['niveau'])

        self.stdout.write(self.style.SUCCESS(
            f"{len(a_corriger)} classe(s) corrigée(s)."
        ))
        self.stdout.write(
            "Les échéanciers vides seront automatiquement renseignés depuis la grille "
            "au prochain ajout de paiement pour ces élèves."
        )
