"""
Rejoue les changements que la synchronisation avait definitivement abandonnes.

Un changement recu est abandonne apres cinq echecs. La cause la plus frequente
etait une collision de numero de recu entre deux postes : le paiement ne
pouvait pas etre enregistre, et disparaissait du poste destinataire sans que
rien ne le signale. La numerotation par poste empeche desormais le probleme de
se reproduire, mais elle ne ramene pas ce qui a deja ete perdu.

Cette commande relit ces changements et les applique. Quand le numero de recu
est deja pris par un AUTRE paiement du poste, elle en attribue un nouveau au
paiement entrant plutot que d'ecraser l'existant : les deux sont de vrais
encaissements, et aucun ne doit disparaitre pour laisser la place a l'autre.
Le tableau des numeros modifies est affiche, car un recu papier peut deja
circuler avec l'ancien.

Par prudence, la commande ne modifie rien sans `--appliquer`.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from synchronisation.engine import apply_sync_change
from synchronisation.models import SyncChange


class Command(BaseCommand):
    help = "Rejoue les changements de synchronisation abandonnes."

    def add_arguments(self, parser):
        parser.add_argument(
            '--appliquer', action='store_true',
            help="Ecrire reellement en base. Sans cette option, la commande "
                 "se contente de montrer ce qu'elle ferait.",
        )
        parser.add_argument(
            '--modele', default='',
            help="Se limiter a un modele, par exemple paiements.Paiement.",
        )

    def handle(self, *args, **options):
        appliquer = options['appliquer']
        modele = (options['modele'] or '').strip()

        changements = SyncChange.objects.filter(statut=SyncChange.STATUT_ABANDONED)
        if modele:
            changements = changements.filter(model_label=modele)
        changements = list(changements.order_by('id'))

        if not changements:
            self.stdout.write("Aucun changement abandonne. Rien a rattraper.")
            return

        self.stdout.write(
            f"{len(changements)} changement(s) abandonne(s) a rejouer."
            + ("" if appliquer else "  [SIMULATION — rien ne sera ecrit]")
        )

        reussis, echecs, renumerotes = 0, [], []

        for changement in changements:
            try:
                with transaction.atomic():
                    nouveau = self._rejouer(changement, appliquer)
                    if not appliquer:
                        # La simulation ne doit rien laisser derriere elle.
                        transaction.set_rollback(True)
                if nouveau:
                    renumerotes.append(nouveau)
                reussis += 1
            except Exception as erreur:
                echecs.append((changement, str(erreur)[:160]))

        self._rapport(reussis, renumerotes, echecs, appliquer)

    def _rejouer(self, changement, appliquer):
        """
        Applique un changement. Retourne (ancien, nouveau) si le numero de recu
        a du etre change, None sinon.
        """
        renumerotage = None

        if changement.model_label == 'paiements.Paiement':
            renumerotage = self._resoudre_collision_de_recu(changement)

        # Le statut repart de zero : `apply_sync_change` le repositionnera a
        # APPLIED en cas de succes, et les tentatives passees ne doivent plus
        # peser sur cette nouvelle chance.
        changement.tentatives = 0
        changement.statut = SyncChange.STATUT_PENDING
        if appliquer:
            changement.save(update_fields=['tentatives', 'statut'])

        apply_sync_change(changement)
        return renumerotage

    def _resoudre_collision_de_recu(self, changement):
        from paiements.models import Paiement
        from paiements.numerotation import prochain_numero

        payload = changement.payload or {}
        numero = payload.get('numero_recu')
        if not numero:
            return None

        occupant = Paiement.objects.filter(numero_recu=numero).first()
        if not occupant:
            return None
        if str(occupant.sync_uuid) == str(changement.object_uuid):
            return None  # c'est le meme paiement, aucune collision

        annee = str(payload.get('date_paiement') or '')[:4]
        try:
            annee = int(annee)
        except ValueError:
            from django.utils import timezone
            annee = timezone.now().year

        remplacant = prochain_numero(Paiement, annee)
        # Le payload est modifie en memoire : c'est lui qu'applique le moteur.
        changement.payload = {**payload, 'numero_recu': remplacant}
        return (numero, remplacant, payload.get('montant'))

    def _rapport(self, reussis, renumerotes, echecs, appliquer):
        self.stdout.write('')
        verbe = 'rejoue' if appliquer else 'rejouable'
        self.stdout.write(self.style.SUCCESS(f"  {reussis} changement(s) {verbe}(s)."))

        if renumerotes:
            self.stdout.write('')
            self.stdout.write(
                "  Numeros de recu modifies (un recu papier peut circuler avec l'ancien) :"
            )
            for ancien, nouveau, montant in renumerotes:
                self.stdout.write(f"    {ancien}  ->  {nouveau}    {montant} GNF")

        if echecs:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f"  {len(echecs)} echec(s) persistant(s) :"))
            for changement, erreur in echecs:
                self.stdout.write(
                    f"    {changement.operation} {changement.model_label} "
                    f"{changement.object_uuid} : {erreur}"
                )

        if not appliquer:
            self.stdout.write('')
            self.stdout.write(
                "  Simulation terminee, aucune ecriture. Relancez avec --appliquer "
                "pour enregistrer."
            )
