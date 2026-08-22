from datetime import datetime
from decimal import Decimal

from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from eleves.models import Classe
from eleves.utils_annee import get_debut_periode_reporting
from utilisateurs.permissions import can_view_reports
from utilisateurs.utils import filter_by_user_school, user_school

from .models import EcheancierPaiement, Paiement, Relance
from .services import calculer_situations_echeanciers


def _parse_date(value, default):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date() if value else default
    except (TypeError, ValueError):
        return default


def _rapport_data(request):
    aujourd_hui = timezone.localdate()
    ecole_utilisateur = user_school(request.user)
    debut_defaut = get_debut_periode_reporting(
        request, ecole_utilisateur, today=aujourd_hui
    )
    date_debut = _parse_date(request.GET.get("date_debut"), debut_defaut)
    date_fin = _parse_date(request.GET.get("date_fin"), aujourd_hui)
    if date_debut > date_fin:
        date_debut, date_fin = date_fin, date_debut

    classe_id = (request.GET.get("classe") or "").strip()
    statut = (request.GET.get("statut") or "VALIDE").strip().upper()
    statuts_valides = {code for code, _label in Paiement.STATUT_CHOICES}
    if statut not in statuts_valides and statut != "TOUS":
        statut = "VALIDE"

    classes = filter_by_user_school(
        Classe.objects.select_related("ecole").order_by("annee_scolaire", "nom"),
        request.user,
        "ecole",
    )
    classe_selectionnee = None
    if classe_id:
        try:
            classe_selectionnee = classes.filter(pk=int(classe_id)).first()
        except (TypeError, ValueError):
            classe_selectionnee = None

    paiements = filter_by_user_school(
        Paiement.objects.select_related(
            "eleve", "eleve__classe", "eleve__classe__ecole",
            "classe_encaissement", "ecole_encaissement",
            "type_paiement", "mode_paiement",
        ),
        request.user,
        "eleve__classe__ecole",
    ).filter(date_paiement__range=(date_debut, date_fin))
    if statut != "TOUS":
        paiements = paiements.filter(statut=statut)
    if classe_selectionnee:
        paiements = paiements.pour_classe(classe_selectionnee)
    paiements = paiements.order_by("eleve__classe__nom", "-date_paiement", "eleve__nom")

    echeanciers = filter_by_user_school(
        EcheancierPaiement.objects.select_related(
            "eleve", "eleve__classe", "eleve__classe__ecole"
        ).filter(
            eleve__statut="ACTIF",
            annee_scolaire=F('eleve__classe__annee_scolaire'),
        ),
        request.user,
        "eleve__classe__ecole",
    )
    if classe_selectionnee:
        echeanciers = echeanciers.filter(eleve__classe=classe_selectionnee)

    retards = []
    echeanciers = list(
        echeanciers.order_by("eleve__classe__nom", "eleve__nom", "eleve__prenom")
    )
    situations = calculer_situations_echeanciers(
        echeanciers, date_reference=date_fin, date_limite=date_fin
    )
    for echeancier in echeanciers:
        montant_retard = situations[echeancier.pk]['retard']
        if montant_retard > 0:
            retards.append({
                "echeancier": echeancier,
                "montant_retard": montant_retard,
            })

    relances = filter_by_user_school(
        Relance.objects.select_related(
            "eleve", "eleve__classe", "eleve__classe__ecole"
        ),
        request.user,
        "eleve__classe__ecole",
    ).filter(date_creation__date__range=(date_debut, date_fin))
    if classe_selectionnee:
        relances = relances.filter(eleve__classe=classe_selectionnee)
    relances = relances.order_by("eleve__classe__nom", "-date_creation")

    paiements_list = list(paiements)
    relances_list = list(relances)
    total_paiements = sum(
        (paiement.montant or Decimal("0") for paiement in paiements_list),
        Decimal("0"),
    )
    total_retards = sum(
        (retard["montant_retard"] for retard in retards), Decimal("0")
    )

    modes = []
    for ligne in paiements.values("mode_paiement__nom").annotate(
        nombre=Count("id"), montant=Sum("montant")
    ).order_by("mode_paiement__nom"):
        montant = ligne["montant"] or Decimal("0")
        modes.append({
            "nom": ligne["mode_paiement__nom"] or "Non renseigné",
            "nombre": ligne["nombre"],
            "montant": montant,
            "pourcentage": (
                montant * Decimal("100") / total_paiements
                if total_paiements else Decimal("0")
            ),
        })

    classes_stats = {}
    for paiement in paiements_list:
        classe = paiement.classe_reference
        ligne = classes_stats.setdefault(classe.id, {
            "classe": classe, "paiements": 0, "montant": Decimal("0"),
            "retards": Decimal("0"), "relances": 0,
        })
        ligne["paiements"] += 1
        ligne["montant"] += paiement.montant or Decimal("0")
    for retard in retards:
        classe = retard["echeancier"].eleve.classe
        ligne = classes_stats.setdefault(classe.id, {
            "classe": classe, "paiements": 0, "montant": Decimal("0"),
            "retards": Decimal("0"), "relances": 0,
        })
        ligne["retards"] += retard["montant_retard"]
    for relance in relances_list:
        classe = relance.eleve.classe
        ligne = classes_stats.setdefault(classe.id, {
            "classe": classe, "paiements": 0, "montant": Decimal("0"),
            "retards": Decimal("0"), "relances": 0,
        })
        ligne["relances"] += 1

    ecole = classe_selectionnee.ecole if classe_selectionnee else ecole_utilisateur
    return {
        "titre_page": "Rapport comptable consolidé",
        "ecole": ecole,
        "classes": classes,
        "classe_selectionnee": classe_selectionnee,
        "classe_id": str(classe_selectionnee.id) if classe_selectionnee else "",
        "date_debut": date_debut,
        "date_fin": date_fin,
        "statut": statut,
        "paiements": paiements_list,
        "retards": retards,
        "relances": relances_list,
        "modes": modes,
        "classes_stats": sorted(
            classes_stats.values(),
            key=lambda ligne: (ligne["classe"].annee_scolaire, ligne["classe"].nom),
        ),
        "total_paiements": total_paiements,
        "total_retards": total_retards,
        "nombre_paiements": len(paiements_list),
        "nombre_retards": len(retards),
        "nombre_relances": len(relances_list),
    }


@can_view_reports
def rapport_comptable(request):
    return render(request, "paiements/rapport_comptable.html", _rapport_data(request))


def export_rapport_comptable_pdf(request):
    """Compatibilité avec le rapport professionnel PDF."""
    from .rapports_professionnels import export_comptabilite_pdf

    query = request.GET.copy()
    query["classe_id"] = query.get("classe", "")
    query["du"] = query.get("date_debut", "")
    query["au"] = query.get("date_fin", "")
    request.GET = query
    return export_comptabilite_pdf(request)


def export_rapport_comptable_excel(request):
    """Compatibilité avec le rapport professionnel Excel."""
    from .rapports_professionnels import export_comptabilite_excel

    query = request.GET.copy()
    query["classe_id"] = query.get("classe", "")
    query["du"] = query.get("date_debut", "")
    query["au"] = query.get("date_fin", "")
    request.GET = query
    return export_comptabilite_excel(request)
