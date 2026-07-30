from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

from utilisateurs.models import Profil


class Command(BaseCommand):
    help = "Create missing Profil objects for existing users (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--default-role",
            type=str,
            default="COMPTABLE",
            choices=["ADMIN", "DIRECTEUR", "COMPTABLE", "SECRETAIRE", "ENSEIGNANT", "SURVEILLANT"],
            help="Role to assign to non-superusers when creating missing profiles. Superusers will always get ADMIN.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Do not write changes, only report what would happen.",
        )
        parser.add_argument(
            "--list-users",
            action="store_true",
            help="List each user missing a profile (use with --dry-run to only report).",
        )

    def handle(self, *args, **options):
        default_role = options["default_role"]
        dry_run = options["dry_run"]
        list_users = options["list_users"]

        users_qs = User.objects.filter(profil__isnull=True).order_by("id")
        total_missing = users_qs.count()
        created = 0

        if total_missing == 0:
            self.stdout.write(self.style.SUCCESS("All users already have a Profil. Nothing to do."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Found {total_missing} user(s) without Profil. Default role: {default_role}. Dry-run: {dry_run}"
            )
        )

        for user in users_qs.iterator():
            role = "ADMIN" if user.is_superuser else default_role
            if list_users:
                self.stdout.write(f"- User #{user.id} {user.username}: create Profil(role={role})")
            if not dry_run:
                try:
                    profil, was_created = Profil.objects.get_or_create(
                        user=user,
                        defaults={'role': role}
                    )
                    if was_created:
                        created += 1
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Failed to create Profil for user {user.id} {user.username}: {e}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"Dry-run complete. Would create {total_missing} Profil(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Created {created} Profil(s) (out of {total_missing} missing)."))
