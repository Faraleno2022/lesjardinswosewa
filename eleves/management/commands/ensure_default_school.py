import os

from django.core.management.base import BaseCommand

from eleves.models import Ecole


class Command(BaseCommand):
    help = "Create a default school for a fresh Render database when none exists."

    def handle(self, *args, **options):
        if Ecole.objects.exists():
            self.stdout.write("Default school setup skipped; at least one school exists.")
            return

        ecole = Ecole.objects.create(
            nom=os.environ.get('MYSCHOOL_DEFAULT_SCHOOL_NAME', 'GS Hadja Kanfing Dian'),
            adresse=os.environ.get('MYSCHOOL_DEFAULT_SCHOOL_ADDRESS', 'Conakry'),
            telephone=os.environ.get('MYSCHOOL_DEFAULT_SCHOOL_PHONE', '+224600000000'),
            directeur=os.environ.get('MYSCHOOL_DEFAULT_SCHOOL_DIRECTOR', 'Direction'),
            etat='VALIDE',
        )
        self.stdout.write(self.style.SUCCESS(f"Default school created with id={ecole.id}."))
