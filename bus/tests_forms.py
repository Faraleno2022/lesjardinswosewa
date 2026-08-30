from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from eleves.models import Classe, Ecole, Eleve

from .forms import AbonnementBusForm, AbonnementCantineForm
from .models import AbonnementBus, AbonnementCantine


class SelectionEleveAbonnementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ecole = Ecole.objects.create(
            nom="École autorisée",
            adresse="Conakry",
            telephone="+224622000001",
            directeur="Direction",
        )
        cls.autre_ecole = Ecole.objects.create(
            nom="Autre école",
            adresse="Conakry",
            telephone="+224622000002",
            directeur="Direction",
        )
        cls.classe_a = Classe.objects.create(
            ecole=cls.ecole,
            nom="1ère année A",
            niveau="PRIMAIRE_1",
            annee_scolaire="2026-2027",
        )
        cls.classe_b = Classe.objects.create(
            ecole=cls.ecole,
            nom="2ème année B",
            niveau="PRIMAIRE_2",
            annee_scolaire="2026-2027",
        )
        cls.classe_interdite = Classe.objects.create(
            ecole=cls.autre_ecole,
            nom="Classe privée",
            niveau="PRIMAIRE_1",
            annee_scolaire="2026-2027",
        )
        cls.eleve_a = Eleve.objects.create(
            matricule="MAT-001",
            prenom="Aminata",
            nom="Camara",
            sexe="F",
            classe=cls.classe_a,
        )
        cls.eleve_b = Eleve.objects.create(
            matricule="MAT-002",
            prenom="Mamadou",
            nom="Diallo",
            sexe="M",
            classe=cls.classe_b,
        )
        cls.eleve_interdit = Eleve.objects.create(
            matricule="AUTRE-001",
            prenom="Ibrahima",
            nom="Barry",
            sexe="M",
            classe=cls.classe_interdite,
        )
        cls.eleve_corbeille = Eleve.objects.create(
            matricule="MAT-CORBEILLE",
            prenom="Fatoumata",
            nom="Keita",
            sexe="F",
            classe=cls.classe_a,
            est_dans_corbeille=True,
        )
        cls.user = User.objects.create_user("comptable", password="secret")
        cls.user.profil.ecole = cls.ecole
        cls.user.profil.telephone = "+224622000003"
        cls.user.profil.save(update_fields=["ecole", "telephone"])

    def test_listes_sont_limitees_a_ecole_et_excluent_corbeille(self):
        form = AbonnementBusForm(user=self.user)

        self.assertQuerySetEqual(
            form.fields["classe"].queryset,
            [self.classe_a, self.classe_b],
            ordered=False,
        )
        self.assertQuerySetEqual(
            form.fields["eleve"].queryset,
            [self.eleve_a, self.eleve_b],
            ordered=False,
        )

    def test_libelle_et_attribut_classe_du_menu_eleve(self):
        form = AbonnementCantineForm(user=self.user)
        html = str(form["eleve"])

        self.assertIn("MAT-001 — AMINATA CAMARA", html)
        self.assertIn(f'data-classe-id="{self.classe_a.pk}"', html)
        self.assertNotIn("AUTRE-001", html)
        self.assertNotIn("MAT-CORBEILLE", html)

    def test_classe_et_eleve_doivent_correspondre(self):
        form = AbonnementBusForm(
            data={
                "classe": self.classe_a.pk,
                "eleve": self.eleve_b.pk,
                "montant": "500000",
                "periodicite": AbonnementBus.Periodicite.ANNUEL,
                "date_debut": "2026-09-01",
                "date_expiration": "2027-09-01",
                "statut": AbonnementBus.Statut.ACTIF,
                "alerte_avant_jours": "7",
            },
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("n'appartient pas à la classe", form.errors["eleve"][0])

    def test_annuel_et_services_horaires_sont_disponibles(self):
        bus_form = AbonnementBusForm(user=self.user)
        cantine_form = AbonnementCantineForm(user=self.user)

        self.assertIn(
            (AbonnementBus.Periodicite.ANNUEL, "Annuel"),
            list(bus_form.fields["periodicite"].choices),
        )
        self.assertIn(
            (AbonnementCantine.Periodicite.ANNUEL, "Annuel"),
            list(cantine_form.fields["periodicite"].choices),
        )
        repas = dict(cantine_form.fields["type_repas"].choices)
        self.assertEqual(repas[AbonnementCantine.TypeRepas.REPAS_10H], "Repas de 10 h")
        self.assertEqual(repas[AbonnementCantine.TypeRepas.REPAS_14H], "Repas de 14 h")

    def test_formulaire_valide_conserve_le_paiement_annuel(self):
        form = AbonnementCantineForm(
            data={
                "classe": self.classe_a.pk,
                "eleve": self.eleve_a.pk,
                "montant": "600000",
                "periodicite": AbonnementCantine.Periodicite.ANNUEL,
                "type_repas": AbonnementCantine.TypeRepas.REPAS_14H,
                "date_debut": date(2026, 9, 1),
                "date_expiration": date(2027, 9, 1),
                "statut": AbonnementCantine.Statut.ACTIF,
                "alerte_avant_jours": "7",
            },
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        abonnement = form.save()
        self.assertEqual(abonnement.periodicite, AbonnementCantine.Periodicite.ANNUEL)
        self.assertEqual(abonnement.type_repas, AbonnementCantine.TypeRepas.REPAS_14H)
