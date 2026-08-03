from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from eleves.models import Classe, Ecole, Eleve
from utilisateurs.models import Profil

from .models_bibliotheque import (
    CategorieLivre,
    Emprunt,
    HistoriqueLivre,
    Livre,
    ParametreBibliotheque,
    Reservation,
)


TEST_MIDDLEWARE = tuple(
    middleware
    for middleware in settings.MIDDLEWARE
    if middleware != 'ecole_moderne.licence_middleware.LicenceMiddleware'
)


@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class ReservationsBibliothequeTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='École Bibliothèque',
            adresse='Conakry',
            telephone='+224620400001',
            directeur='Direction',
        )
        self.autre_ecole = Ecole.objects.create(
            nom='Autre École Bibliothèque',
            adresse='Kindia',
            telephone='+224620400002',
            directeur='Autre direction',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole,
            nom='7ème A',
            niveau='COLLEGE_7',
            annee_scolaire='2026-2027',
        )
        self.autre_classe = Classe.objects.create(
            ecole=self.autre_ecole,
            nom='7ème B',
            niveau='COLLEGE_7',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='BIB-001',
            prenom='Aminata',
            nom='Diallo',
            sexe='F',
            classe=self.classe,
            statut='ACTIF',
        )
        self.autre_eleve_meme_ecole = Eleve.objects.create(
            matricule='BIB-002',
            prenom='Mamadou',
            nom='Camara',
            sexe='M',
            classe=self.classe,
            statut='ACTIF',
        )
        self.eleve_autre_ecole = Eleve.objects.create(
            matricule='AUT-BIB-001',
            prenom='Fatou',
            nom='Condé',
            sexe='F',
            classe=self.autre_classe,
            statut='ACTIF',
        )

        User = get_user_model()
        self.user = User.objects.create_user(
            'bibliothecaire', password='pass12345'
        )
        self.autre_user = User.objects.create_user(
            'autre_bibliothecaire', password='pass12345'
        )
        Profil.objects.update_or_create(
            user=self.user,
            defaults={
                'role': 'ADMIN',
                'ecole': self.ecole,
                'telephone': '+224620400011',
                'is_validated': True,
            },
        )
        Profil.objects.update_or_create(
            user=self.autre_user,
            defaults={
                'role': 'ADMIN',
                'ecole': self.autre_ecole,
                'telephone': '+224620400012',
                'is_validated': True,
            },
        )
        self.client.force_login(self.user)

        self.categorie = CategorieLivre.objects.create(
            nom='Romans', code='ROM-BIB'
        )
        self.livre = Livre.objects.create(
            code_livre='LIV-BIB-001',
            titre='Le livre disponible',
            auteur='Auteur Test',
            categorie=self.categorie,
            emplacement='Rayon A',
            nombre_exemplaires=1,
            exemplaires_disponibles=1,
            statut='DISPONIBLE',
            cree_par=self.user,
        )
        self.livre_indisponible = Livre.objects.create(
            code_livre='LIV-BIB-002',
            titre='Le livre emprunté',
            auteur='Auteur Test',
            categorie=self.categorie,
            emplacement='Rayon B',
            nombre_exemplaires=1,
            exemplaires_disponibles=0,
            statut='EMPRUNTE',
            cree_par=self.user,
        )
        self.livre_autre_ecole = Livre.objects.create(
            code_livre='LIV-AUT-001',
            titre='Livre autre école',
            auteur='Auteur Externe',
            categorie=self.categorie,
            emplacement='Rayon C',
            nombre_exemplaires=1,
            exemplaires_disponibles=1,
            statut='DISPONIBLE',
            cree_par=self.autre_user,
        )
        self.params = ParametreBibliotheque.objects.create(
            duree_emprunt_defaut=14,
            duree_reservation_defaut=7,
            nombre_emprunts_max=3,
            nombre_reservations_max=2,
            modifie_par=self.user,
        )

    def _reservation(self, livre=None, eleve=None, statut='EN_ATTENTE', numero=None):
        return Reservation.objects.create(
            numero_reservation=numero or f'RES-TEST-{Reservation.objects.count() + 1:04d}',
            livre=livre or self.livre,
            eleve=eleve or self.eleve,
            date_expiration=timezone.now() + timedelta(days=7),
            statut=statut,
            date_notification=timezone.now() if statut == 'DISPONIBLE' else None,
            cree_par=self.user,
        )

    def test_creation_reservation_disponible(self):
        response = self.client.post(reverse('depenses:creer_reservation'), {
            'livre': self.livre.pk,
            'eleve': self.eleve.pk,
            'observations': 'À remettre au secrétariat',
        })

        self.assertRedirects(response, reverse('depenses:liste_reservations'))
        reservation = Reservation.objects.get(eleve=self.eleve, livre=self.livre)
        self.assertTrue(reservation.numero_reservation.startswith('RES-'))
        self.assertEqual(reservation.statut, 'DISPONIBLE')
        self.assertIsNotNone(reservation.date_notification)
        self.assertTrue(
            HistoriqueLivre.objects.filter(
                livre=self.livre, action='RESERVATION'
            ).exists()
        )

    def test_livre_indisponible_cree_une_file_d_attente(self):
        response = self.client.post(reverse('depenses:creer_reservation'), {
            'livre': self.livre_indisponible.pk,
            'eleve': self.eleve.pk,
            'observations': '',
        })

        self.assertRedirects(response, reverse('depenses:liste_reservations'))
        reservation = Reservation.objects.get(
            eleve=self.eleve, livre=self.livre_indisponible
        )
        self.assertEqual(reservation.statut, 'EN_ATTENTE')
        self.assertIsNone(reservation.date_notification)

    def test_doublon_et_limite_sont_refuses(self):
        self._reservation(livre=self.livre_indisponible)
        response = self.client.post(reverse('depenses:creer_reservation'), {
            'livre': self.livre_indisponible.pk,
            'eleve': self.eleve.pk,
            'observations': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'possède déjà une réservation active')
        self.assertEqual(Reservation.objects.count(), 1)

        self.params.nombre_reservations_max = 1
        self.params.save(update_fields=['nombre_reservations_max'])
        response = self.client.post(reverse('depenses:creer_reservation'), {
            'livre': self.livre.pk,
            'eleve': self.eleve.pk,
            'observations': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'a atteint la limite de 1 réservations actives')
        self.assertEqual(Reservation.objects.count(), 1)

    def test_formulaire_et_liste_sont_isoles_par_ecole(self):
        reservation_externe = Reservation.objects.create(
            numero_reservation='RES-AUT-0001',
            livre=self.livre_autre_ecole,
            eleve=self.eleve_autre_ecole,
            date_expiration=timezone.now() + timedelta(days=7),
            statut='DISPONIBLE',
            cree_par=self.autre_user,
        )

        response = self.client.get(reverse('depenses:creer_reservation'))
        self.assertContains(response, self.livre.titre)
        self.assertNotContains(response, self.livre_autre_ecole.titre)
        self.assertNotContains(response, self.eleve_autre_ecole.matricule)

        response = self.client.get(reverse('depenses:liste_reservations'))
        self.assertNotContains(response, reservation_externe.numero_reservation)

        response = self.client.post(reverse('depenses:creer_reservation'), {
            'livre': self.livre_autre_ecole.pk,
            'eleve': self.eleve.pk,
            'observations': '',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Reservation.objects.count(), 1)

        annulation_externe = self.client.post(
            reverse(
                'depenses:annuler_reservation',
                args=[reservation_externe.pk],
            )
        )
        self.assertEqual(annulation_externe.status_code, 404)
        reservation_externe.refresh_from_db()
        self.assertEqual(reservation_externe.statut, 'DISPONIBLE')

    def test_liste_et_dashboard_expirent_les_reservations_depassees(self):
        reservation = self._reservation(statut='DISPONIBLE')
        Reservation.objects.filter(pk=reservation.pk).update(
            date_expiration=timezone.now() - timedelta(minutes=1)
        )

        response = self.client.get(reverse('depenses:liste_reservations'))
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.statut, 'EXPIREE')

        Reservation.objects.filter(pk=reservation.pk).update(
            statut='EN_ATTENTE',
            date_expiration=timezone.now() - timedelta(minutes=1),
        )
        response = self.client.get(reverse('depenses:dashboard_bibliotheque'))
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.statut, 'EXPIREE')

    def test_annulation_promeut_la_reservation_suivante(self):
        premiere = self._reservation(statut='DISPONIBLE', numero='RES-TEST-0001')
        suivante = self._reservation(
            eleve=self.autre_eleve_meme_ecole,
            statut='EN_ATTENTE',
            numero='RES-TEST-0002',
        )

        get_response = self.client.get(
            reverse('depenses:annuler_reservation', args=[premiere.pk])
        )
        self.assertEqual(get_response.status_code, 405)

        response = self.client.post(
            reverse('depenses:annuler_reservation', args=[premiere.pk])
        )
        self.assertRedirects(response, reverse('depenses:liste_reservations'))
        premiere.refresh_from_db()
        suivante.refresh_from_db()
        self.assertEqual(premiere.statut, 'ANNULEE')
        self.assertEqual(suivante.statut, 'DISPONIBLE')
        self.assertIsNotNone(suivante.date_notification)

    def test_reservation_disponible_devient_un_emprunt(self):
        reservation = self._reservation(statut='DISPONIBLE')
        response = self.client.post(reverse('depenses:creer_emprunt'), {
            'livre': self.livre.pk,
            'eleve': self.eleve.pk,
            'reservation': reservation.pk,
            'duree_jours': 14,
        })

        self.assertRedirects(response, reverse('depenses:liste_emprunts'))
        reservation.refresh_from_db()
        self.livre.refresh_from_db()
        self.assertEqual(reservation.statut, 'EMPRUNTEE')
        self.assertEqual(self.livre.exemplaires_disponibles, 0)
        self.assertEqual(self.livre.statut, 'EMPRUNTE')
        self.assertTrue(
            Emprunt.objects.filter(
                livre=self.livre, eleve=self.eleve, statut='EN_COURS'
            ).exists()
        )

    def test_reservation_prioritaire_bloque_un_autre_eleve(self):
        self._reservation(statut='DISPONIBLE')
        response = self.client.post(reverse('depenses:creer_emprunt'), {
            'livre': self.livre.pk,
            'eleve': self.autre_eleve_meme_ecole.pk,
            'duree_jours': 14,
        })

        self.assertRedirects(response, reverse('depenses:liste_reservations'))
        self.assertFalse(Emprunt.objects.exists())

    def test_retour_livre_active_la_premiere_reservation(self):
        reservation = self._reservation(
            livre=self.livre_indisponible,
            statut='EN_ATTENTE',
        )
        emprunt = Emprunt.objects.create(
            numero_emprunt='EMP-TEST-0001',
            livre=self.livre_indisponible,
            eleve=self.autre_eleve_meme_ecole,
            date_emprunt=date.today(),
            date_retour_prevue=date.today() + timedelta(days=14),
            statut='EN_COURS',
            cree_par=self.user,
        )

        response = self.client.post(
            reverse('depenses:retourner_livre', args=[emprunt.pk]),
            {'etat_retour': 'BON', 'observations': ''},
        )

        self.assertRedirects(response, reverse('depenses:liste_emprunts'))
        reservation.refresh_from_db()
        self.assertEqual(reservation.statut, 'DISPONIBLE')
        self.assertIsNotNone(reservation.date_notification)
