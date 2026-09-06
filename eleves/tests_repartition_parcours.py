from datetime import date
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from paiements.models import Paiement, TypePaiement, ModePaiement
from paiements.tests.support import TEST_MIDDLEWARE
from .models import Ecole, Classe, Eleve, GrilleTarifaire


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RepartitionParcoursTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('dispatch', 'test@example.com', 'test')
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(nom='Répartition', adresse='Conakry', telephone='620000001', directeur='Direction', etat='VALIDE')
        self.a = self.classe('Petite section A')
        self.b = self.classe('Petite section B')
        self.c = self.classe('Petite section C')
        self.autre_niveau = self.classe('Grande section A', niveau='GRANDE_SECTION')
        self.autre_annee = self.classe('Petite section ancienne', annee_scolaire='2025-2026')
        self.autre_ecole = Ecole.objects.create(nom='Autre école', adresse='Conakry', telephone='620000002', directeur='Direction')
        self.externe = self.classe('Petite section externe', ecole=self.autre_ecole)
        self.eleve = Eleve.objects.create(prenom='Aminata', nom='Diallo', sexe='F', matricule='DISP-001', classe=self.a, statut='EN_ATTENTE')
        GrilleTarifaire.objects.create(ecole=self.ecole, niveau=self.a.niveau, annee_scolaire=self.a.annee_scolaire,
                                      frais_inscription=30000, frais_reinscription=20000, tranche_1=100000, tranche_2=100000, tranche_3=100000)
        self.type = TypePaiement.objects.create(nom='Inscription', categorie='SCOLARITE')
        self.mode = ModePaiement.objects.create(nom='Espèces')
        self.url = reverse('eleves:repartir_eleves')

    def classe(self, nom, **kwargs):
        valeurs = dict(ecole=self.ecole, niveau='PETITE_SECTION', annee_scolaire='2026-2027')
        valeurs.update(kwargs)
        return Classe.objects.create(nom=nom, **valeurs)

    def affecter(self, destination=None, action='enregistrer', **kwargs):
        donnees = dict(eleve_id=self.eleve.pk, ancienne_classe_id=self.eleve.classe_id,
                       classe_id=(destination or self.b).pk, action=action)
        donnees.update(kwargs)
        return self.client.post(self.url, donnees)

    def paiement(self, **kwargs):
        valeurs = dict(eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
                       montant=10000, statut='EN_ATTENTE', annee_scolaire='2026-2027', date_paiement=date.today())
        valeurs.update(kwargs)
        return Paiement.objects.create(**valeurs)

    def test_options_meme_niveau_ecole_annee(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        ligne = list(response.context['page_obj'])[0]
        self.assertEqual({c.pk for c in ligne.classes_repartition}, {self.a.pk, self.b.pk, self.c.pk})
        self.assertContains(response, 'premier paiement')

    def test_affectation_individuelle_puis_paiement_avec_retour(self):
        autre = Eleve.objects.create(prenom='Autre', nom='Élève', sexe='M', matricule='DISP-002', classe=self.a)
        response = self.affecter(action='payer')
        self.eleve.refresh_from_db()
        autre.refresh_from_db()
        self.assertEqual(self.eleve.classe_id, self.b.pk)
        self.assertEqual(autre.classe_id, self.a.pk)
        self.assertEqual(self.eleve.statut, 'EN_ATTENTE')
        self.assertTrue(self.eleve.historique.exists())
        self.assertEqual(urlparse(response.url).path, reverse('paiements:ajouter_paiement_eleve', args=[self.eleve.pk]))
        self.assertEqual(parse_qs(urlparse(response.url).query)['next'], [self.url])
        paiement_page = self.client.get(response.url)
        self.assertEqual(paiement_page.status_code, 200)
        self.assertTrue(paiement_page.context['form'].fields['eleve'].queryset.filter(pk=self.eleve.pk).exists())

    def test_destination_invalide_et_modification_concurrente_refusees(self):
        for classe in (self.externe, self.autre_annee, self.autre_niveau):
            with self.subTest(classe=classe.pk):
                self.assertEqual(self.affecter(classe).status_code, 404)
        self.assertEqual(self.affecter(ancienne_classe_id=self.c.pk).status_code, 302)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.classe_id, self.a.pk)
        self.assertEqual(self.affecter(eleve_id='incorrect').status_code, 400)

    def test_paiement_en_attente_reutilise(self):
        paiement = self.paiement()
        response = self.affecter(action='payer')
        self.assertEqual(urlparse(response.url).path, reverse('paiements:detail_paiement', args=[paiement.pk]))
        self.assertEqual(Paiement.objects.filter(eleve=self.eleve).count(), 1)

    @patch('paiements.views.send_enrollment_confirmation')
    @patch('paiements.views.send_payment_receipt')
    def test_premier_paiement_valide_confirme_et_retourne_au_dispatch(self, _receipt, _confirmation):
        self.affecter()
        self.eleve.refresh_from_db()
        response = self.client.post(reverse('paiements:ajouter_paiement_eleve', args=[self.eleve.pk]), {
            'eleve': self.eleve.pk, 'type_paiement': self.type.pk, 'mode_paiement': self.mode.pk,
            'montant': '30000', 'date_paiement': date.today().isoformat(), 'next': self.url,
        })
        self.assertEqual(response.status_code, 302)
        paiement = Paiement.objects.get(eleve=self.eleve)
        self.assertEqual(paiement.statut, 'EN_ATTENTE')
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.statut, 'EN_ATTENTE')
        response = self.client.post(reverse('paiements:valider_paiement', args=[paiement.pk]), {'next': self.url})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url)
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.statut, 'ACTIF')
        self.assertTrue(list(self.client.get(self.url).context['page_obj'])[0].premier_paiement_valide)
        paiement.refresh_from_db()
        paiement.statut = 'ANNULE'
        paiement.save()
        self.assertFalse(list(self.client.get(self.url).context['page_obj'])[0].premier_paiement_valide)

    def test_cantine_ancienne_annee_et_paiement_en_attente_ne_confirment_pas(self):
        cantine = TypePaiement.objects.create(nom='Cantine', categorie='CANTINE')
        self.paiement(type_paiement=cantine, statut='VALIDE')
        self.paiement(annee_scolaire='2025-2026', statut='VALIDE')
        self.paiement()
        self.eleve.refresh_from_db()
        self.assertEqual(self.eleve.statut, 'EN_ATTENTE')
        self.assertFalse(list(self.client.get(self.url).context['page_obj'])[0].premier_paiement_valide)

    def test_import_lot_precis_sans_responsable_et_reimport_conserve_statut(self):
        fichier = SimpleUploadedFile('import.csv', 'Prénom,Nom,Sexe\nFanta,Barry,F\n'.encode('utf-8'), content_type='text/csv')
        response = self.client.post(reverse('eleves:importer_eleves'), {'classe_id': self.a.pk, 'generer_matricules': 'on', 'fichier': fichier})
        self.assertEqual(response.url, self.url)
        nouveau = Eleve.objects.get(prenom='Fanta')
        self.assertEqual(nouveau.statut, 'EN_ATTENTE')
        self.assertEqual(self.client.session['dernier_import_eleves'], [nouveau.pk])
        self.assertEqual([e.pk for e in self.client.get(self.url).context['page_obj']], [nouveau.pk])
        self.assertEqual(len(self.client.get(self.url + '?tous=1').context['page_obj']), 2)

    def test_isolation_ecole_et_permission(self):
        comptable = get_user_model().objects.create_user('comptable-dispatch', password='test')
        comptable.profil.ecole = self.ecole
        comptable.profil.role = 'COMPTABLE'
        comptable.profil.is_validated = True
        comptable.profil.save()
        externe = Eleve.objects.create(prenom='Secret', nom='Autre', sexe='F', matricule='EXT-001', classe=self.externe)
        self.client.force_login(comptable)
        self.assertNotContains(self.client.get(self.url + '?tous=1'), 'EXT-001')
        self.assertEqual(self.affecter(eleve_id=externe.pk).status_code, 404)
        comptable.profil.role = 'ENSEIGNANT'
        comptable.profil.peut_importer_eleves = False
        comptable.profil.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)
