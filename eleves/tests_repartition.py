from datetime import date
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from paiements.models import Paiement, TypePaiement, ModePaiement
from paiements.tests.support import TEST_MIDDLEWARE
from .models import Classe, Ecole, Eleve, GrilleTarifaire


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class RepartitionImportTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('repartition', '', 'secret')
        self.client.force_login(self.user)
        self.ecole = Ecole.objects.create(nom='Ecole', adresse='Conakry', telephone='620000000', directeur='Direction', etat='VALIDE')
        self.a = self.classe('Petite section A')
        self.b = self.classe('Petite section B')
        self.c = self.classe('Petite section C')
        self.autre_niveau = self.classe('Grande section', niveau='GRANDE_SECTION')
        self.autre_annee = self.classe('Petite section ancienne', annee_scolaire='2025-2026')
        self.autre_ecole = Ecole.objects.create(nom='Autre ecole', adresse='Conakry', telephone='620000001', directeur='Direction', etat='VALIDE')
        self.externe = self.classe('Petite section externe', ecole=self.autre_ecole)
        GrilleTarifaire.objects.create(ecole=self.ecole, niveau='PETITE_SECTION', annee_scolaire='2026-2027', frais_inscription=50000, frais_reinscription=30000, tranche_1=500000, tranche_2=0, tranche_3=0)
        self.url = reverse('eleves:repartir_eleves')
        self.type = TypePaiement.objects.create(nom='Inscription', categorie='SCOLARITE')
        self.mode = ModePaiement.objects.create(nom='Espèces')

    def classe(self, nom, **kwargs):
        data = {'ecole': self.ecole, 'niveau': 'PETITE_SECTION', 'annee_scolaire': '2026-2027'}
        data.update(kwargs)
        return Classe.objects.create(nom=nom, **data)

    def importer(self):
        fichier = SimpleUploadedFile('eleves.csv', 'Prénom,Nom,Sexe\nAminata,Diallo,F\nMoussa,Bah,M\n'.encode('utf-8'), content_type='text/csv')
        response = self.client.post(reverse('eleves:importer_eleves'), {'classe_id': self.a.pk, 'generer_matricules': 'on', 'fichier': fichier})
        self.assertRedirects(response, self.url)
        return Eleve.objects.get(prenom='Aminata')

    def payer(self, eleve, **kwargs):
        data = dict(eleve=eleve, type_paiement=self.type, mode_paiement=self.mode, montant=50000, date_paiement=date.today(), annee_scolaire='2026-2027', statut='VALIDE')
        data.update(kwargs)
        return Paiement.objects.create(**data)

    def test_import_repartition_paiement_activation(self):
        eleve = self.importer()
        self.assertEqual(eleve.statut, 'EN_ATTENTE')
        self.assertEqual(len(self.client.session['dernier_import_eleves']), 2)
        page = self.client.get(self.url)
        ligne = next(e for e in page.context['page_obj'] if e.pk == eleve.pk)
        self.assertEqual({c.pk for c in ligne.classes_repartition}, {self.a.pk, self.b.pk, self.c.pk})
        response = self.client.post(self.url, {'eleve_id': eleve.pk, 'ancienne_classe_id': self.a.pk, 'classe_id': self.b.pk, 'action': 'payer'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(urlparse(response.url).path, reverse('paiements:ajouter_paiement_eleve', args=[eleve.pk]))
        self.assertEqual(parse_qs(urlparse(response.url).query)['next'], [self.url])
        eleve.refresh_from_db()
        self.assertEqual(eleve.classe_id, self.b.pk)
        self.assertEqual(eleve.statut, 'EN_ATTENTE')
        self.assertTrue(eleve.historique.exists())
        self.assertEqual(eleve.echeancier.total_du, 550000)
        self.assertEqual(Eleve.objects.get(prenom='Moussa').classe_id, self.a.pk)
        paiement = self.payer(eleve, statut='EN_ATTENTE')
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'EN_ATTENTE')
        paiement.statut = 'VALIDE'
        paiement.save()
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'ACTIF')
        self.assertEqual(eleve.echeancier.total_paye, 50000)

    def test_classes_incompatibles_et_ecran_perime_refuses(self):
        eleve = self.importer()
        for classe in (self.autre_niveau, self.autre_annee, self.externe):
            response = self.client.post(self.url, {'eleve_id': eleve.pk, 'ancienne_classe_id': self.a.pk, 'classe_id': classe.pk, 'action': 'enregistrer'})
            self.assertEqual(response.status_code, 404)
        self.client.post(self.url, {'eleve_id': eleve.pk, 'ancienne_classe_id': self.a.pk, 'classe_id': self.b.pk, 'action': 'enregistrer'})
        self.client.post(self.url, {'eleve_id': eleve.pk, 'ancienne_classe_id': self.a.pk, 'classe_id': self.c.pk, 'action': 'enregistrer'})
        eleve.refresh_from_db()
        self.assertEqual(eleve.classe_id, self.b.pk)

    def test_seul_paiement_scolaire_valide_de_la_bonne_annee_active(self):
        eleve = self.importer()
        cantine = TypePaiement.objects.create(nom='Cantine', categorie='CANTINE')
        self.payer(eleve, type_paiement=cantine)
        self.payer(eleve, annee_scolaire='2025-2026')
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'EN_ATTENTE')
        self.payer(eleve)
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'ACTIF')
        self.importer()
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'ACTIF')

    def test_isolation_ecole_et_permissions(self):
        eleve = self.importer()
        user = get_user_model().objects.create_user('autre-admin', password='secret')
        user.profil.role = 'ADMIN'
        user.profil.ecole = self.autre_ecole
        user.profil.save()
        self.client.force_login(user)
        page = self.client.get(self.url)
        self.assertNotContains(page, eleve.nom_complet)
        response = self.client.post(self.url, {'eleve_id': eleve.pk, 'ancienne_classe_id': self.a.pk, 'classe_id': self.b.pk, 'action': 'enregistrer'})
        self.assertEqual(response.status_code, 404)
        user.profil.role = 'ENSEIGNANT'
        user.profil.peut_importer_eleves = False
        user.profil.save()
        self.assertEqual(self.client.get(self.url).status_code, 403)


    @patch('paiements.views.send_enrollment_confirmation')
    @patch('paiements.views.send_payment_receipt')
    def test_premier_paiement_depuis_formulaire_et_retour(self, recu, confirmation):
        eleve = self.importer()
        payer_url = reverse('paiements:ajouter_paiement_eleve', args=[eleve.pk])
        page = self.client.get(payer_url)
        self.assertEqual(page.status_code, 200)
        self.assertTrue(page.context['form'].fields['eleve'].queryset.filter(pk=eleve.pk).exists())
        response = self.client.post(payer_url, {
            'eleve': eleve.pk, 'type_paiement': self.type.pk,
            'mode_paiement': self.mode.pk, 'montant': '50000',
            'date_paiement': date.today().isoformat(), 'next': self.url,
        })
        self.assertEqual(response.status_code, 302)
        paiement = Paiement.objects.get(eleve=eleve)
        self.assertEqual(paiement.statut, 'EN_ATTENTE')
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'EN_ATTENTE')
        # Reprendre le reçu existant évite un doublon lors du retour à la liste.
        reprise = self.client.post(self.url, {'eleve_id': eleve.pk,
            'ancienne_classe_id': self.a.pk, 'classe_id': self.a.pk, 'action': 'payer'})
        self.assertEqual(urlparse(reprise.url).path, reverse('paiements:detail_paiement', args=[paiement.pk]))
        response = self.client.post(reverse('paiements:valider_paiement', args=[paiement.pk]), {'next': self.url})
        self.assertRedirects(response, self.url)
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'ACTIF')

    def test_reimport_ne_reactive_pas_un_dossier_suspendu(self):
        eleve = self.importer()
        eleve.statut = 'SUSPENDU'
        eleve.save()
        self.importer()
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'SUSPENDU')
        self.payer(eleve)
        eleve.refresh_from_db()
        self.assertEqual(eleve.statut, 'SUSPENDU')
