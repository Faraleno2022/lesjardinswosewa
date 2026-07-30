from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test import RequestFactory
from paiements.views import liste_eleves_soldes
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware

class Command(BaseCommand):
    help = 'Debug la vue liste_eleves_soldes'

    def handle(self, *args, **options):
        self.stdout.write("=== DEBUG ÉLÈVES SOLDÉS VIA MANAGEMENT COMMAND ===")
        
        # Créer une requête factice avec un host valide
        factory = RequestFactory()
        request = factory.get('/paiements/eleves-soldes/', HTTP_HOST='localhost')
        
        # Ajouter un utilisateur admin
        try:
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                user = User.objects.create_superuser('debug_admin', 'admin@test.com', 'debug123')
                self.stdout.write(f"Utilisateur admin créé: {user.username}")
            else:
                self.stdout.write(f"Utilisateur admin trouvé: {user.username}")
        except Exception as e:
            self.stdout.write(f"Erreur création utilisateur: {e}")
            return
        
        request.user = user
        
        # Ajouter les middlewares nécessaires
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        
        AuthenticationMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        
        # Marquer l'utilisateur comme authentifié
        request.user.is_authenticated = True
        
        try:
            # Appeler la vue directement
            self.stdout.write("Appel de la vue liste_eleves_soldes...")
            response = liste_eleves_soldes(request)
            
            self.stdout.write(f"Status code: {response.status_code}")
            
            if response.status_code == 200:
                content = response.content.decode('utf-8')
                self.stdout.write(f"Contenu reçu: {len(content)} caractères")
                
                # Chercher les informations de debug
                if "DEBUG:" in content:
                    lines = content.split('\n')
                    for line in lines:
                        if "DEBUG:" in line:
                            self.stdout.write(f"Template debug: {line.strip()}")
                
                # Vérifier la présence du tableau
                if '<tbody>' in content:
                    tbody_start = content.find('<tbody>')
                    tbody_end = content.find('</tbody>')
                    if tbody_start != -1 and tbody_end != -1:
                        tbody_content = content[tbody_start:tbody_end]
                        # Compter les vraies lignes d'élèves (pas les détails)
                        lines = tbody_content.split('\n')
                        eleve_rows = 0
                        for line in lines:
                            if '<tr>' in line and 'student-details' not in line:
                                eleve_rows += 1
                        self.stdout.write(f"Lignes d'élèves dans le tableau: {eleve_rows}")
                        
                        # Afficher un extrait du tbody
                        self.stdout.write("Extrait du tbody:")
                        self.stdout.write(tbody_content[:500] + "...")
                else:
                    self.stdout.write("Aucun tableau trouvé dans la réponse")
                    
            else:
                self.stdout.write(f"Erreur HTTP {response.status_code}")
                if hasattr(response, 'content'):
                    self.stdout.write(response.content.decode('utf-8')[:500])
                    
        except Exception as e:
            self.stdout.write(f"Erreur lors de l'appel de la vue: {e}")
            import traceback
            traceback.print_exc()
