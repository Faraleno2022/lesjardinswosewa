"""Les métadonnées publiques doivent suivre le domaine qui sert la page.

Un lien de lesjardinswosewa.com partagé sur WhatsApp, Facebook ou LinkedIn
annonçait le logiciel hôte au lieu de l'école sur toutes les pages qui ne
redéfinissaient pas explicitement leurs blocs SEO.
"""

from django.test import SimpleTestCase, override_settings

from ecole_moderne.identite_site import identite_pour_hote


HOTE_ECOLE = 'www.lesjardinswosewa.com'
HOTE_LOGICIEL = 'www.myschoolgn.space'


class IdentiteParDomaineTests(SimpleTestCase):
    def test_le_domaine_de_lecole_est_reconnu_avec_ou_sans_www(self):
        for hote in ('lesjardinswosewa.com', HOTE_ECOLE, 'LESJARDINSWOSEWA.COM'):
            with self.subTest(hote=hote):
                self.assertTrue(identite_pour_hote(hote)['est_ecole'])

    def test_tout_autre_domaine_reste_sur_lidentite_du_logiciel(self):
        for hote in (HOTE_LOGICIEL, 'localhost:8000', '', None):
            with self.subTest(hote=hote):
                self.assertFalse(identite_pour_hote(hote)['est_ecole'])


@override_settings(ALLOWED_HOSTS=[HOTE_ECOLE, HOTE_LOGICIEL])
class MetadonneesPartageesTests(SimpleTestCase):
    """L'espace parents ne redéfinit aucun bloc SEO : il expose les valeurs par défaut.

    C'est le cas de l'immense majorité des gabarits du projet : seules huit
    pages sur près de deux cents redéfinissent leurs balises.
    """

    URL = '/rapport-scolaire/'

    def _html(self, hote):
        reponse = self.client.get(self.URL, HTTP_HOST=hote)
        self.assertEqual(reponse.status_code, 200)
        return reponse.content.decode('utf-8')

    def test_le_domaine_de_lecole_nannonce_jamais_le_logiciel(self):
        html = self._html(HOTE_ECOLE)

        self.assertIn('Les Jardins Wosewa', html)
        for marque_logiciel in ('Myschool', 'MySchoolGN', 'G.S HKD'):
            self.assertNotIn(marque_logiciel, html)

    def test_le_domaine_de_lecole_publie_des_donnees_structurees_decole(self):
        html = self._html(HOTE_ECOLE)

        self.assertIn('"@type": "School"', html)
        self.assertNotIn('SoftwareApplication', html)
        self.assertNotIn('myschoolgn.space', html)

    def test_le_domaine_du_logiciel_garde_ses_propres_metadonnees(self):
        html = self._html(HOTE_LOGICIEL)

        self.assertIn('Myschool', html)
        self.assertIn('"@type": "SoftwareApplication"', html)
        self.assertNotIn('Les Jardins Wosewa', html)


@override_settings(ALLOWED_HOSTS=[HOTE_ECOLE, HOTE_LOGICIEL])
class SitemapParDomaineTests(SimpleTestCase):
    def test_le_sitemap_de_lecole_ignore_les_pages_commerciales(self):
        xml = self.client.get('/sitemap.xml', HTTP_HOST=HOTE_ECOLE).content.decode()

        self.assertIn('/campus/conakry/', xml)
        self.assertIn('/campus/siguiri/', xml)
        for page_logiciel in ('/tarifs/', '/demo/', '/contact/', '/fonctionnalites/'):
            self.assertNotIn(page_logiciel, xml)

    def test_le_sitemap_du_logiciel_ignore_les_campus(self):
        xml = self.client.get('/sitemap.xml', HTTP_HOST=HOTE_LOGICIEL).content.decode()

        self.assertIn('/tarifs/', xml)
        self.assertNotIn('/campus/', xml)


@override_settings(ALLOWED_HOSTS=[HOTE_ECOLE, HOTE_LOGICIEL])
class PagesCommercialesTests(SimpleTestCase):
    """Les pages qui vendent le logiciel ne doivent pas être référencées
    sous le domaine de l'école."""

    PAGES = ('/tarifs/', '/demo/', '/contact/', '/fonctionnalites/')

    def test_noindex_sur_le_domaine_de_lecole(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.client.get(page, HTTP_HOST=HOTE_ECOLE).content.decode()
                self.assertIn('content="noindex,follow"', html)

    def test_indexables_sur_le_domaine_du_logiciel(self):
        for page in self.PAGES:
            with self.subTest(page=page):
                html = self.client.get(page, HTTP_HOST=HOTE_LOGICIEL).content.decode()
                self.assertIn('content="index,follow"', html)
