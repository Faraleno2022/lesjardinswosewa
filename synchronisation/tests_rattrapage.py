"""
Rattrapage des changements abandonnes.

Le scenario reproduit ici est celui observe sur un poste reel : 14 paiements
recus d'un autre poste, tous refuses sur la contrainte d'unicite du numero de
recu, puis abandonnes — donc absents de la base sans aucun signalement.
"""
from datetime import date
from decimal import Decimal
from io import StringIO
from uuid import uuid4

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from eleves.models import Classe, Ecole, Eleve
from paiements.models import ModePaiement, Paiement, TypePaiement

from .engine import serialize_instance
from .models import SyncChange


class RattrapageTests(TestCase):
    def setUp(self):
        self.ecole = Ecole.objects.create(
            nom='Ecole Rattrapage', adresse='Conakry', telephone='+224600000040',
            directeur='Direction', etat='VALIDE',
        )
        self.classe = Classe.objects.create(
            ecole=self.ecole, nom='CE1', niveau='PRIMAIRE_2',
            annee_scolaire='2026-2027',
        )
        self.eleve = Eleve.objects.create(
            matricule='EL-0100', nom='Bah', prenom='Mamadou',
            date_naissance=date(2017, 2, 11), classe=self.classe,
            date_inscription=date(2026, 9, 1),
        )
        self.type = TypePaiement.objects.create(nom='Scolarite')
        self.mode = ModePaiement.objects.create(nom='Especes')

    def _paiement_local(self, numero, montant='500000'):
        paiement = Paiement.objects.create(
            eleve=self.eleve, type_paiement=self.type, mode_paiement=self.mode,
            montant=Decimal(montant), date_paiement=timezone.now().date(),
            annee_scolaire='2026-2027', statut='VALIDE',
        )
        Paiement.objects.filter(pk=paiement.pk).update(numero_recu=numero)
        paiement.refresh_from_db()
        return paiement

    def _changement_abandonne(self, numero, montant='730000'):
        """Un paiement venu d'un autre poste, refuse puis abandonne."""
        modele = self._paiement_local(numero='TEMPORAIRE-1', montant=montant)
        charge = serialize_instance(modele)
        charge['numero_recu'] = numero
        uuid_distant = uuid4()
        charge['sync_uuid'] = str(uuid_distant)
        modele.delete()

        return SyncChange.objects.create(
            ecole=self.ecole, model_label='paiements.Paiement',
            object_uuid=uuid_distant, operation='CREATE', payload=charge,
            statut=SyncChange.STATUT_ABANDONED, tentatives=5,
            erreur='UNIQUE constraint failed: paiements_paiement.numero_recu',
        )

    def _lancer(self, *arguments):
        sortie = StringIO()
        call_command('rattraper_changements_abandonnes', *arguments, stdout=sortie)
        return sortie.getvalue()

    def test_la_simulation_n_ecrit_rien(self):
        occupant = self._paiement_local('REC20260001')
        self._changement_abandonne('REC20260001')
        avant = Paiement.objects.count()

        texte = self._lancer('--modele', 'paiements.Paiement')

        self.assertIn('SIMULATION', texte)
        self.assertEqual(Paiement.objects.count(), avant)
        occupant.refresh_from_db()
        self.assertEqual(occupant.numero_recu, 'REC20260001')
        self.assertEqual(
            SyncChange.objects.get(pk=self._dernier_changement().pk).statut,
            SyncChange.STATUT_ABANDONED,
        )

    def _dernier_changement(self):
        return SyncChange.objects.filter(
            model_label='paiements.Paiement',
        ).order_by('-id').first()

    def test_le_paiement_perdu_est_recupere_avec_un_nouveau_numero(self):
        """
        Les deux encaissements sont reels : aucun ne doit disparaitre pour
        laisser sa place a l'autre.
        """
        occupant = self._paiement_local('REC20260001', montant='2750000')
        changement = self._changement_abandonne('REC20260001', montant='730000')

        texte = self._lancer('--modele', 'paiements.Paiement', '--appliquer')

        recupere = Paiement.objects.filter(sync_uuid=changement.object_uuid).first()
        self.assertIsNotNone(recupere, "le paiement perdu doit etre revenu")
        self.assertEqual(recupere.montant, Decimal('730000'))

        # L'occupant garde son numero et son montant : il n'a pas ete ecrase.
        occupant.refresh_from_db()
        self.assertEqual(occupant.numero_recu, 'REC20260001')
        self.assertEqual(occupant.montant, Decimal('2750000'))

        # Le nouveau numero est different, et le rapport le signale.
        self.assertNotEqual(recupere.numero_recu, 'REC20260001')
        self.assertIn('REC20260001', texte)
        self.assertIn(recupere.numero_recu, texte)

    def test_un_changement_rejoue_cesse_d_etre_abandonne(self):
        self._paiement_local('REC20260002')
        changement = self._changement_abandonne('REC20260002')

        self._lancer('--modele', 'paiements.Paiement', '--appliquer')

        changement.refresh_from_db()
        self.assertEqual(changement.statut, SyncChange.STATUT_APPLIED)

    def test_sans_collision_le_numero_d_origine_est_conserve(self):
        """Un recu deja imprime doit garder son numero partout ou il arrive."""
        changement = self._changement_abandonne('REC20260777')

        self._lancer('--modele', 'paiements.Paiement', '--appliquer')

        recupere = Paiement.objects.get(sync_uuid=changement.object_uuid)
        self.assertEqual(recupere.numero_recu, 'REC20260777')

    def test_rien_a_rattraper_se_dit_clairement(self):
        texte = self._lancer()
        self.assertIn('Aucun changement abandonne', texte)
