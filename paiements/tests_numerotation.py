"""
Numerotation des recus entre plusieurs postes.

Le defaut couvert ici a coute 14 paiements sur un poste reel : deux caisses
generaient le meme numero, et le paiement arrivant par synchronisation etait
abandonne sur la contrainte d'unicite.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from eleves.models import Classe, Ecole, Eleve
from paiements.models import ModePaiement, Paiement, TypePaiement
from paiements.numerotation import (
    code_du_poste,
    prefixe_courant,
    prochain_numero,
    sequence_de,
)


POSTE_A = '11111111-1111-1111-1111-111111111111'
POSTE_B = '22222222-2222-2222-2222-222222222222'


class CodeDuPosteTests(TestCase):
    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_un_poste_relie_a_un_code(self):
        code = code_du_poste()
        self.assertIsNotNone(code)
        self.assertEqual(len(code), 4)
        self.assertTrue(all(c in '0123456789ABCDEF' for c in code))

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_le_code_ne_change_jamais_pour_un_meme_poste(self):
        """
        Un code qui bougerait recreerait le probleme qu'il resout : la sequence
        repartirait a 1 sur des numeros deja pris.
        """
        self.assertEqual(code_du_poste(), code_du_poste())

    def test_deux_postes_ont_des_codes_differents(self):
        with override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A):
            code_a = code_du_poste()
        with override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_B):
            code_b = code_du_poste()
        self.assertNotEqual(code_a, code_b)

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID='')
    def test_un_poste_isole_garde_le_format_court(self):
        """Sans synchronisation, la base n'est partagee avec personne."""
        self.assertIsNone(code_du_poste())
        self.assertEqual(prefixe_courant(2026), 'REC2026')

    def test_les_deux_formats_sont_relus(self):
        self.assertEqual(sequence_de('REC20260007'), 7)
        self.assertEqual(sequence_de('REC2026-A3F7-0012'), 12)
        self.assertIsNone(sequence_de('n-importe-quoi'))
        self.assertIsNone(sequence_de(None))


class NumerotationPaiementTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Recus', adresse='Conakry', telephone='+224600000030',
            directeur='Direction', etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='CP', niveau='PRIMAIRE_1',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='EL-0001', nom='Diallo', prenom='Aissatou',
            date_naissance=date(2018, 5, 3), classe=self.classe,
            date_inscription=date(2026, 9, 1),
        )
        self.type = TypePaiement.objects.create(nom='Scolarite')
        self.mode = ModePaiement.objects.create(nom='Especes')

    def _payer(self, montant=100000):
        return Paiement.objects.create(
            eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=Decimal(montant), date_paiement=timezone.now().date(),
            annee_scolaire='2026-2027', statut='VALIDE',
        )

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_le_numero_porte_le_code_du_poste(self):
        paiement = self._payer()
        annee = timezone.now().year
        self.assertTrue(paiement.numero_recu.startswith(f'REC{annee}-'))
        self.assertEqual(sequence_de(paiement.numero_recu), 1)

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_la_sequence_avance_sur_un_meme_poste(self):
        premier = self._payer()
        second = self._payer(200000)
        self.assertEqual(sequence_de(premier.numero_recu), 1)
        self.assertEqual(sequence_de(second.numero_recu), 2)

    def test_deux_postes_ne_produisent_jamais_le_meme_numero(self):
        """
        Le coeur du probleme : avant, les deux premiers paiements de chaque
        poste s'appelaient tous les deux REC20260001, et le second a arriver
        par synchronisation etait perdu.
        """
        with override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A):
            depuis_a = self._payer()
        with override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_B):
            depuis_b = self._payer(250000)

        self.assertNotEqual(depuis_a.numero_recu, depuis_b.numero_recu)
        # Chacun repart bien de 1 dans son propre espace de numerotation.
        self.assertEqual(sequence_de(depuis_a.numero_recu), 1)
        self.assertEqual(sequence_de(depuis_b.numero_recu), 1)

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_les_numeros_d_un_autre_poste_ne_font_pas_avancer_la_sequence(self):
        """
        Sinon deux postes se pousseraient mutuellement vers le haut a chaque
        synchronisation, et les numeros deviendraient illisibles.
        """
        with override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_B):
            for _ in range(5):
                self._payer()

        suivant = prochain_numero(Paiement, timezone.now().year)
        self.assertEqual(sequence_de(suivant), 1)

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_un_numero_deja_pose_n_est_pas_regenere(self):
        """Un paiement recu par synchronisation garde le numero de son emetteur."""
        paiement = Paiement(
            eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=Decimal('50000'), date_paiement=timezone.now().date(),
            annee_scolaire='2026-2027', statut='VALIDE',
            numero_recu='REC2026-BEEF-0042',
        )
        paiement.save()
        paiement.refresh_from_db()
        self.assertEqual(paiement.numero_recu, 'REC2026-BEEF-0042')

    @override_settings(MYSCHOOL_SYNC_DEVICE_ID=POSTE_A)
    def test_les_anciens_numeros_cohabitent_sans_gener(self):
        """Les paiements deja enregistres ne sont pas renumerotes."""
        ancien = self._payer()
        Paiement.objects.filter(pk=ancien.pk).update(numero_recu='REC20260099')

        nouveau = self._payer(300000)

        self.assertEqual(sequence_de(nouveau.numero_recu), 1)
        self.assertTrue(Paiement.objects.filter(numero_recu='REC20260099').exists())
