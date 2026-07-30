from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from django.contrib.auth.models import User
from eleves.models import Ecole, Classe, GrilleTarifaire, Eleve, Responsable
from paiements.models import TypePaiement, ModePaiement, Paiement
from paiements.views import ensure_echeancier_for_eleve, _auto_validate_echeancier_for_eleve


class Command(BaseCommand):
    help = "Test: enregistrer une Réinscription puis une Inscription, et vérifier allocations"

    def add_arguments(self, parser):
        parser.add_argument('--ecole', type=str, default='ECOLE TEST REINSCRIPTION')
        parser.add_argument('--niveau', type=str, default=None, help='Code niveau (par défaut: premier de NIVEAUX_CHOICES)')
        parser.add_argument('--annee', type=str, default=None, help='Année scolaire auto si absent')

    def handle(self, *args, **opts):
        ecole_nom = opts['ecole']
        ecole, _ = Ecole.objects.get_or_create(
            nom=ecole_nom,
            defaults=dict(adresse='Test', telephone='+224620000000', directeur='Test')
        )
        # Niveau
        if opts['niveau']:
            niveau_code = opts['niveau']
        else:
            niveau_code = Classe.NIVEAUX_CHOICES[0][0]
        # Année
        today = timezone.now().date()
        annee = opts['annee'] or (f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}")

        # Classe
        classe, _ = Classe.objects.get_or_create(
            ecole=ecole,
            niveau=niveau_code,
            annee_scolaire=annee,
            defaults=dict(nom=dict(Classe.NIVEAUX_CHOICES).get(niveau_code, 'Classe Test'))
        )

        # Grille (inscription != réinscription)
        grille, _ = GrilleTarifaire.objects.get_or_create(
            ecole=ecole, niveau=niveau_code, annee_scolaire=annee,
            defaults=dict(
                frais_inscription=Decimal('30000'),
                frais_reinscription=Decimal('20000'),
                tranche_1=Decimal('100000'),
                tranche_2=Decimal('100000'),
                tranche_3=Decimal('100000'),
            )
        )

        # Responsable principal (requis par le modèle)
        resp, _ = Responsable.objects.get_or_create(
            prenom='Parent', nom='Test', relation='PERE',
            defaults=dict(telephone='+224620000001', adresse='Test')
        )

        # Élève (champs requis)
        today = timezone.now().date()
        eleve, _ = Eleve.objects.get_or_create(
            nom='Eleve', prenom='Test', classe=classe,
            defaults=dict(
                matricule=f'TEST-{timezone.now().strftime("%H%M%S")}',
                sexe='M',
                date_naissance=today.replace(year=today.year - 10),
                lieu_naissance='Conakry',
                date_inscription=today,
                responsable_principal=resp,
            )
        )

        # Mode Paiement (par défaut: Espèces)
        mode, _ = ModePaiement.objects.get_or_create(nom='Espèces', defaults=dict(description='Paiement en espèces'))

        # Types de paiements
        t_reinsc_t1, _ = TypePaiement.objects.get_or_create(nom='Réinscription + Tranche 1', defaults=dict(actif=True))
        t_insc, _ = TypePaiement.objects.get_or_create(nom="Frais d'inscription", defaults=dict(actif=True))

        # 1) Réinscription + T1
        ech = ensure_echeancier_for_eleve(eleve, created_by=None, prefer_reinscription=True)
        montant1 = int((grille.frais_reinscription or 0) + (grille.tranche_1 or 0))
        p1 = Paiement.objects.create(
            eleve=eleve,
            type_paiement=t_reinsc_t1,
            mode_paiement=mode,
            montant=montant1,
            date_paiement=today,
            statut='VALIDE',
            numero_recu='',
        )
        _auto_validate_echeancier_for_eleve(eleve)

        # 2) Inscription (après réinscription)
        # S'assurer que l'échéancier existe
        ensure_echeancier_for_eleve(eleve, created_by=None)
        montant2 = int(grille.frais_inscription or 0)
        p2 = Paiement.objects.create(
            eleve=eleve,
            type_paiement=t_insc,
            mode_paiement=mode,
            montant=montant2,
            date_paiement=today,
            statut='VALIDE',
            numero_recu='',
        )
        _auto_validate_echeancier_for_eleve(eleve)

        # Recalculer restants
        ech = getattr(eleve, 'echeancier', None)
        if not ech:
            self.stdout.write(self.style.ERROR('Aucun échéancier pour le test.'))
            return

        # Afficher synthèse
        def fmt(n):
            try:
                return f"{int(n):,}".replace(',', ' ')
            except Exception:
                return str(n)

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== SYNTHÈSE APRÈS DEUX PAIEMENTS ==='))
        self.stdout.write(f"École: {ecole.nom} | Classe: {classe.nom} | Élève: {eleve.nom_complet}")
        self.stdout.write(f"Grille: Inscription={fmt(grille.frais_inscription)} | Réinscription={fmt(grille.frais_reinscription)} | T1={fmt(grille.tranche_1)}")

        self.stdout.write(self.style.HTTP_INFO('\nPaiement 1: Réinscription + Tranche 1'))
        self.stdout.write(f"Montant: {fmt(montant1)} GNF | Statut: {p1.statut}")

        self.stdout.write(self.style.HTTP_INFO('Paiement 2: Inscription (après Réinscription)'))
        self.stdout.write(f"Montant: {fmt(montant2)} GNF | Statut: {p2.statut}\n")

        # État de l'échéancier
        self.stdout.write(self.style.SQL_TABLE('Échéancier (dus / payés):'))
        self.stdout.write(f"{ 'Réinscription/Inscription':<28} : {fmt(ech.frais_inscription_du)} / {fmt(ech.frais_inscription_paye)}")
        self.stdout.write(f"{ '1ère tranche':<28} : {fmt(ech.tranche_1_due)} / {fmt(ech.tranche_1_payee)}")
        self.stdout.write(f"{ '2ème tranche':<28} : {fmt(ech.tranche_2_due)} / {fmt(ech.tranche_2_payee)}")
        self.stdout.write(f"{ '3ème tranche':<28} : {fmt(ech.tranche_3_due)} / {fmt(ech.tranche_3_payee)}")
        self.stdout.write(f"Statut: {ech.statut}")

        # Attendus logiques:
        # - Après P1, frais_inscription_du = frais_reinscription, T1 due couverte
        # - Après P2 (Inscription), la colonne "inscription" augmente côté payée sans dépasser le dû
        # Si incohérences détectées, l'utilisateur pourra ajuster la grille/flux.
        self.stdout.write(self.style.SUCCESS('\nTest terminé. Vérifiez les valeurs ci-dessus.'))
