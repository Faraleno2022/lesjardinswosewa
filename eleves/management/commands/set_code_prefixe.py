from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from eleves.models import Ecole, _normalize_code_prefixe
import re


def derive_prefix_from_name(name: str) -> str:
    """Derive a short school prefix from the school name.
    Example: "Al Furqan International" -> "AL-FUR"
    Rules:
    - Split on non-letters, keep first 2 significant words.
    - From word1: take up to 2 letters (all if <=2)
    - From word2: take up to 3 letters (all if <=3)
    - Uppercase and join with '-'.
    - Return without trailing slash, caller can append '/' if needed.
    """
    if not name:
        return ""
    words = [w for w in re.split(r"[^A-Za-zÀ-ÖØ-öø-ÿ]+", name) if w]
    if not words:
        return ""
    part1 = words[0][:2]
    part2 = words[1][:3] if len(words) > 1 else ""
    prefix = "-".join(filter(None, [part1, part2])).upper()
    return prefix


class Command(BaseCommand):
    help = (
        "Définir rapidement code_prefixe pour les écoles.\n"
        "Par défaut, DRY-RUN (aucune écriture). Utilisez --apply pour enregistrer.\n"
        "Options: --auto pour dériver depuis le nom, ou --ecole-id/--prefix pour cibler une école."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--auto", action="store_true", help="Dériver et définir automatiquement les préfixes manquants pour toutes les écoles")
        parser.add_argument("--ecole-id", type=int, help="ID d'une école à traiter spécifiquement")
        parser.add_argument("--prefix", type=str, help="Préfixe explicite à définir pour l'école ciblée (ex: AL-FUR)")
        parser.add_argument("--apply", action="store_true", help="Appliquer réellement les changements")
        parser.add_argument("--normalize", action="store_true", help="Normaliser les préfixes existants (éviter doublons, assurer un seul '/')")

    def handle(self, *args, **options):
        auto = options.get("auto", False)
        ecole_id = options.get("ecole_id")
        prefix = (options.get("prefix") or "").strip()
        apply = options.get("apply", False)
        normalize = options.get("normalize", False)

        if ecole_id and not prefix and not auto and not normalize:
            self.stderr.write(self.style.ERROR("Si vous utilisez --ecole-id, fournissez --prefix ou --auto."))
            return

        # Ciblage des écoles
        if ecole_id:
            qs = Ecole.objects.filter(pk=ecole_id)
        else:
            qs = Ecole.objects.all()

        if auto and not ecole_id:
            # Mode auto global: cibler uniquement celles sans code_prefixe
            qs = qs.filter(code_prefixe__isnull=True) | qs.filter(code_prefixe="")

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Aucune école ciblée."))
            return

        total = 0
        updated = 0

        with transaction.atomic():
            for ecole in qs.order_by("nom"):
                total += 1
                current = (ecole.code_prefixe or "").strip()
                if normalize and current:
                    normalized = _normalize_code_prefixe(current)
                    if current == normalized:
                        self.stdout.write(f"{ecole.id} - {ecole.nom}: déjà normalisé '{current}'")
                        continue
                    if apply:
                        ecole.code_prefixe = normalized
                        ecole.save(update_fields=["code_prefixe"])
                    updated += 1
                    self.stdout.write(f"{ecole.id} - {ecole.nom}: normalisé '{current}' -> '{normalized}'")
                    continue

                new_prefix = prefix
                if auto:
                    # Dériver à partir du nom si non défini (ou si ciblage direct auto)
                    if not new_prefix:
                        new_prefix = derive_prefix_from_name(ecole.nom)
                if not new_prefix:
                    self.stdout.write(f"{ecole.id} - {ecole.nom}: aucun préfixe proposé")
                    continue
                normalized = (new_prefix or '').rstrip("/") + "/"
                if current == normalized:
                    self.stdout.write(f"{ecole.id} - {ecole.nom}: déjà '{current}'")
                    continue
                if apply:
                    ecole.code_prefixe = normalized
                    ecole.save(update_fields=["code_prefixe"])
                updated += 1
                self.stdout.write(f"{ecole.id} - {ecole.nom}: '{current or '—'}' -> '{normalized}'")

            if apply:
                self.stdout.write(self.style.SUCCESS(f"Terminé. {updated} école(s) mise(s) à jour sur {total}."))
            else:
                self.stdout.write(self.style.WARNING(f"DRY-RUN: {updated} mise(s) à jour potentielle(s) sur {total}. Utilisez --apply pour enregistrer."))
