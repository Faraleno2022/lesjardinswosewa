from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Classe, Ecole, Eleve


TEST_MIDDLEWARE = tuple(
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware != 'ecole_moderne.licence_middleware.LicenceMiddleware'
)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ChoixApresAjoutEleveTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin-test',
            email='admin@example.com',
            password='test-password',
        )
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(
            nom='École Test',
            adresse='Conakry',
            telephone='+224622000000',
            directeur='Direction',
            etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='8ème A',
            niveau='COLLEGE_8',
            code_matricule='CL8',
            annee_scolaire='2025-2026',
        )

    def test_ajout_eleve_redirige_vers_le_choix(self):
        response = self.client.post(
            reverse('eleves:ajouter_eleve'),
            {
                'prenom': 'ALPHONS',
                'nom': 'THÉA',
                'sexe': 'M',
                'classe': self.classe.id,
                'date_inscription': '2026-08-03',
                'statut': 'ACTIF',
            },
        )

        eleve = Eleve.objects.get(prenom='ALPHONS', nom='THÉA')
        self.assertRedirects(
            response,
            reverse(
                'eleves:choix_apres_ajout_eleve', args=[eleve.id]
            ),
            fetch_redirect_response=False,
        )

    def test_page_propose_paiement_ou_nouvel_eleve(self):
        eleve = Eleve.objects.create(
            matricule='CL8-002',
            prenom='ALPHONS',
            nom='THÉA',
            sexe='M',
            classe=self.classe,
        )

        response = self.client.get(
            reverse('eleves:choix_apres_ajout_eleve', args=[eleve.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ajouter un paiement')
        self.assertContains(response, "Continuer l’ajout des élèves")

        url_continuer = response.context['url_continuer']
        self.assertEqual(
            url_continuer,
            f"{reverse('eleves:ajouter_eleve')}?classe_id={self.classe.id}",
        )

        url_paiement = response.context['url_paiement']
        paiement_query = parse_qs(urlparse(url_paiement).query)
        self.assertEqual(paiement_query['next'], [url_continuer])
        self.assertEqual(
            urlparse(url_paiement).path,
            reverse('paiements:ajouter_paiement_eleve', args=[eleve.id]),
        )
