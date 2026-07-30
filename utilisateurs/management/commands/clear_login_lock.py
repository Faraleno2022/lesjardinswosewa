from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache


class Command(BaseCommand):
    help = (
        "Deverrouille un compte: efface les verrous custom (cache) ET django-axes "
        "(base de donnees) pour une IP et/ou un username. "
        "Exemple: python manage.py clear_login_lock --username admin"
    )

    def add_arguments(self, parser):
        parser.add_argument('--ip', type=str, help='Adresse IP a deverrouiller (ex: 127.0.0.1)')
        parser.add_argument('--username', type=str, help='Nom d utilisateur (insensible a la casse)')
        parser.add_argument('--all', action='store_true', help='Tout deverrouiller (custom + axes)')

    def handle(self, *args, **options):
        ip = options.get('ip')
        username = (options.get('username') or '')
        clear_all = options.get('all')

        if not ip and not username and not clear_all:
            raise CommandError('Fournir au moins --ip, --username ou --all')

        # ---- 1) Verrou custom (cache) ----
        keys = []
        if clear_all:
            try:
                for k in list(getattr(cache, '_cache', {}).keys()):
                    if isinstance(k, str) and (k.startswith('failed_login_') or k.startswith('blocked_login_')):
                        keys.append(k)
            except Exception:
                pass
        elif ip and username:
            uname = username.lower()
            keys += [
                f'failed_login_{ip}', f'failed_login_{ip}_{uname}',
                f'blocked_login_{ip}', f'blocked_login_{ip}_{uname}',
            ]
        elif ip:
            keys += [f'failed_login_{ip}', f'blocked_login_{ip}']
        else:  # username seul
            uname = username.lower()
            try:
                for k in list(getattr(cache, '_cache', {}).keys()):
                    if isinstance(k, str) and (k.endswith(f'_{uname}') or k.startswith('failed_login_') or k.startswith('blocked_login_')):
                        keys.append(k)
            except Exception:
                self.stdout.write(self.style.WARNING(
                    "Cache sans introspection; le verrou axes (ci-dessous) reste efface."
                ))

        cleared = 0
        for k in set(keys):
            try:
                if cache.get(k) is not None:
                    cache.delete(k)
                    cleared += 1
            except Exception:
                pass

        # ---- 2) Verrou django-axes (base de donnees) = le verrou REEL en prod ----
        axes_cleared = 0
        try:
            from axes.utils import reset as axes_reset
            if clear_all:
                axes_cleared = axes_reset() or 0
            else:
                if username:
                    axes_cleared += axes_reset(username=username) or 0
                if ip:
                    axes_cleared += axes_reset(ip=ip) or 0
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'Reset axes impossible: {e}'))

        self.stdout.write(self.style.SUCCESS(
            f'Deverrouille: {cleared} cle(s) cache + {axes_cleared} verrou(x) axes.'
        ))
