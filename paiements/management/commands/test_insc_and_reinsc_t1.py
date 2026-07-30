from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from eleves.models import Ecole, Classe, GrilleTarifaire, Eleve, Responsable
from paiements.models import TypePaiement, ModePaiement, Paiement
from paiements.views import ensure_echeancier_for_eleve, _auto_validate_echeancier_for_eleve


class Command(BaseCommand):
    help = "Test: creer 2 paiements - (1) Inscription + 1ere tranche, (2) Reinscription + Tranche 1 - et afficher les URLs de recus"

    def handle(self, *args, **opts):
        today = timezone.now().date()
        annee = f"{today.year}-{today.year+1}" if today.month >= 9 else f"{today.year-1}-{today.year}"

        # Ecole, classe, grille
        ecole, _ = Ecole.objects.get_or_create(
            nom='ECOLE TEST REINSCRIPTION',
            defaults=dict(adresse='Test', telephone='+224620000000', directeur='Test')
        )
        niveau_code = Classe.NIVEAUX_CHOICES[0][0]
        classe, _ = Classe.objects.get_or_create(
            ecole=ecole, niveau=niveau_code, annee_scolaire=annee,
            defaults=dict(nom='Garderie')
        )
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

        # Responsable
        resp, _ = Responsable.objects.get_or_create(
            prenom='Parent', nom='Test', relation='PERE',
            defaults=dict(telephone='+224620000001', adresse='Test')
        )

        # Eleves A et B
        def create_eleve(suffix):
            now = timezone.now()
            matricule = f"TEST-{suffix}-{now.strftime('%H%M%S')}"
            return Eleve.objects.create(
                nom='Eleve', prenom=f'Test{suffix}', classe=classe,
                matricule=matricule,
                sexe='M', date_naissance=today.replace(year=today.year - 10),
                lieu_naissance='Conakry', date_inscription=today,
                responsable_principal=resp,
            )

        eleve_a = create_eleve('A')
        eleve_b = create_eleve('B')

        # Mode paiement (Especes)
        mode, _ = ModePaiement.objects.get_or_create(nom='Espèces', defaults=dict(description='Paiement en espèces'))

        # Types de paiement (get_or_create securise)
        t_insc_t1, _ = TypePaiement.objects.get_or_create(
            nom="Frais d'inscription + 1ère tranche",
            defaults=dict(description="Inscription + T1", actif=True)
        )
        t_reinsc_t1, _ = TypePaiement.objects.get_or_create(
            nom='Réinscription + Tranche 1',
            defaults=dict(description='Réinscription + T1', actif=True)
        )

        # (1) Eleve A: Inscription + 1ere tranche
        ech_a = ensure_echeancier_for_eleve(eleve_a, created_by=None)
        montant_a = int((grille.frais_inscription or 0) + (grille.tranche_1 or 0))
        p_a = Paiement.objects.create(
            eleve=eleve_a, type_paiement=t_insc_t1, mode_paiement=mode,
            montant=montant_a, date_paiement=today, statut='VALIDE'
        )
        _auto_validate_echeancier_for_eleve(eleve_a)

        # (2) Eleve B: Reinscription + T1
        ech_b = ensure_echeancier_for_eleve(eleve_b, created_by=None, prefer_reinscription=True)
        montant_b = int((grille.frais_reinscription or 0) + (grille.tranche_1 or 0))
        p_b = Paiement.objects.create(
            eleve=eleve_b, type_paiement=t_reinsc_t1, mode_paiement=mode,
            montant=montant_b, date_paiement=today, statut='VALIDE'
        )
        _auto_validate_echeancier_for_eleve(eleve_b)

        # Afficher resultats + URLs de recu
        def url_for(pid):
            return f"/paiements/recu/{pid}/pdf/"

        self.stdout.write("\nPAIEMENT A - Inscription + 1ere tranche")
        self.stdout.write(f"Eleve: {eleve_a.nom_complet} | Paiement id: {p_a.id}")
        self.stdout.write(f"URL recu: {url_for(p_a.id)}")

        self.stdout.write("\nPAIEMENT B - Reinscription + Tranche 1")
        self.stdout.write(f"Eleve: {eleve_b.nom_complet} | Paiement id: {p_b.id}")
        self.stdout.write(f"URL recu: {url_for(p_b.id)}")
