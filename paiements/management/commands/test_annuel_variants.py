from django.core.management.base import BaseCommand
from django.utils import timezone
from decimal import Decimal

from eleves.models import Ecole, Classe, GrilleTarifaire, Eleve, Responsable
from paiements.models import TypePaiement, ModePaiement, Paiement
from paiements.views import ensure_echeancier_for_eleve, _auto_validate_echeancier_for_eleve


class Command(BaseCommand):
    help = "Test: creer 2 paiements - (1) Inscription + Annuel, (2) Reinscription + Annuel - et afficher les URLs de recus"

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

        # Eleves C et D
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

        eleve_c = create_eleve('C')
        eleve_d = create_eleve('D')

        # Mode paiement (Especes)
        mode, _ = ModePaiement.objects.get_or_create(nom='Espèces', defaults=dict(description='Paiement en espèces'))

        # Types de paiement (get_or_create securise)
        t_insc_annuel, _ = TypePaiement.objects.get_or_create(
            nom="Frais d'inscription + Annuel",
            defaults=dict(description="Inscription + Annuel", actif=True)
        )
        t_reinsc_annuel, _ = TypePaiement.objects.get_or_create(
            nom='Réinscription + Annuel',
            defaults=dict(description='Réinscription + Annuel', actif=True)
        )

        # (1) Eleve C: Inscription + Annuel (inscription + T1+T2+T3)
        ech_c = ensure_echeancier_for_eleve(eleve_c, created_by=None)
        montant_c = int((grille.frais_inscription or 0) + int(grille.tranche_1 or 0) + int(grille.tranche_2 or 0) + int(grille.tranche_3 or 0))
        p_c = Paiement.objects.create(
            eleve=eleve_c, type_paiement=t_insc_annuel, mode_paiement=mode,
            montant=montant_c, date_paiement=today, statut='VALIDE'
        )
        _auto_validate_echeancier_for_eleve(eleve_c)

        # (2) Eleve D: Reinscription + Annuel (reinscription + T1+T2+T3)
        ech_d = ensure_echeancier_for_eleve(eleve_d, created_by=None, prefer_reinscription=True)
        montant_d = int((grille.frais_reinscription or 0) + int(grille.tranche_1 or 0) + int(grille.tranche_2 or 0) + int(grille.tranche_3 or 0))
        p_d = Paiement.objects.create(
            eleve=eleve_d, type_paiement=t_reinsc_annuel, mode_paiement=mode,
            montant=montant_d, date_paiement=today, statut='VALIDE'
        )
        _auto_validate_echeancier_for_eleve(eleve_d)

        # Afficher resultats + URLs de recu
        def url_for(pid):
            return f"/paiements/recu/{pid}/pdf/"

        self.stdout.write("\nPAIEMENT C - Inscription + Annuel")
        self.stdout.write(f"Eleve: {eleve_c.nom_complet} | Paiement id: {p_c.id}")
        self.stdout.write(f"URL recu: {url_for(p_c.id)}")

        self.stdout.write("\nPAIEMENT D - Reinscription + Annuel")
        self.stdout.write(f"Eleve: {eleve_d.nom_complet} | Paiement id: {p_d.id}")
        self.stdout.write(f"URL recu: {url_for(p_d.id)}")
