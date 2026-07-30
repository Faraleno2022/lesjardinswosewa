import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the first admin user from environment variables."

    def handle(self, *args, **options):
        username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username or not password:
            self.stdout.write(
                "DJANGO_SUPERUSER_USERNAME or DJANGO_SUPERUSER_PASSWORD not set; "
                "skipping admin user setup."
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
            },
        )

        changed_fields = []
        if email and user.email != email:
            user.email = email
            changed_fields.append("email")
        if not user.is_staff:
            user.is_staff = True
            changed_fields.append("is_staff")
        if not user.is_superuser:
            user.is_superuser = True
            changed_fields.append("is_superuser")
        if not user.is_active:
            user.is_active = True
            changed_fields.append("is_active")

        user.set_password(password)
        changed_fields.append("password")
        user.save()

        profil = getattr(user, "profil", None)
        if profil:
            profil.role = "ADMIN"
            profil.is_validated = True
            profil.actif = True
            profil.peut_gerer_utilisateurs = True
            profil.peut_valider_paiements = True
            profil.peut_valider_depenses = True
            profil.peut_generer_rapports = True
            profil.allowed_menus = [
                "eleves",
                "paiements",
                "depenses",
                "salaires",
                "bus",
                "rapports",
                "administration",
            ]
            profil.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Admin user {username!r} {action}."))
