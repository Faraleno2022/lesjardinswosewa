"""Consultation dynamique des élèves et soldes par mode d'encaissement."""

from collections import defaultdict
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Max, Q, Sum
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date

from eleves.models import Classe, Ecole
from eleves.utils_annee import get_annee_active
from utilisateurs.permissions import can_view_reports
from utilisateurs.utils import filter_by_user_school, user_school

from .models import EcheancierPaiement, ModePaiement, Paiement
from .services import calculer_situations_echeanciers


ZERO = Decimal("0")


def _date_filter(value, default):
    return parse_date((value or "").strip()) or default


def _situation_label(situation):
    if situation is None:
        return "Sans échéancier", "sans_echeancier"
    total_due = Decimal(str(situation["total_du"] or 0))
    paid = Decimal(str(situation["encaisse"] or 0))
    discount = Decimal(str(situation["remises"] or 0))
    remaining = Decimal(str(situation["reste"] or 0))
    if total_due <= 0:
        return "Échéancier vide", "sans_echeancier"
    if remaining <= 0:
        label = "Soldé - remise appliquée" if discount else "Soldé"
        return label, "solde"
    if paid + discount > 0:
        label = "Partiel - remise appliquée" if discount else "Partiel"
        return label, "reste"
    return "À payer", "reste"


def _filter_options(request, selected_school_id, selected_year):
    classes = filter_by_user_school(
        Classe.objects.select_related("ecole").order_by(
            "ecole__nom", "-annee_scolaire", "niveau", "nom"
        ),
        request.user,
        "ecole",
    )
    schools = Ecole.objects.filter(
        pk__in=classes.order_by().values("ecole_id")
    ).order_by("nom")
    years = list(
        classes.values_list("annee_scolaire", flat=True)
        .distinct()
        .order_by("-annee_scolaire")
    )
    visible_classes = classes
    if selected_school_id:
        visible_classes = visible_classes.filter(ecole_id=selected_school_id)
    if selected_year:
        visible_classes = visible_classes.filter(annee_scolaire=selected_year)
    return {
        "schools": list(schools),
        "classes": list(classes),
        "visible_class_ids": set(visible_classes.values_list("id", flat=True)),
        "years": years,
        "modes": list(ModePaiement.objects.order_by("nom")),
    }


def _payment_modes_detail_data(request):
    today = timezone.localdate()
    default_start = today.replace(day=1)
    start = _date_filter(
        request.GET.get("date_debut") or request.GET.get("du"), default_start
    )
    end = min(
        _date_filter(request.GET.get("date_fin") or request.GET.get("au"), today),
        today,
    )
    if start > end:
        start, end = end, start

    accessible_classes = filter_by_user_school(
        Classe.objects.select_related("ecole"), request.user, "ecole"
    )
    school_value = (request.GET.get("ecole_id") or "").strip()
    class_value = (
        request.GET.get("classe_id") or request.GET.get("classe") or ""
    ).strip()
    selected_class = None
    if class_value.isdigit():
        selected_class = accessible_classes.filter(pk=int(class_value)).first()

    selected_school_id = None
    if selected_class:
        selected_school_id = selected_class.ecole_id
    elif school_value.isdigit() and accessible_classes.filter(
        ecole_id=int(school_value)
    ).exists():
        selected_school_id = int(school_value)
    else:
        school = user_school(request.user)
        selected_school_id = school.pk if school else None

    requested_year = (request.GET.get("annee_scolaire") or "").strip()
    if requested_year:
        selected_year = requested_year
    elif selected_class:
        selected_year = selected_class.annee_scolaire
    else:
        selected_school = (
            Ecole.objects.filter(pk=selected_school_id).first()
            if selected_school_id else None
        )
        selected_year = get_annee_active(request, selected_school) or (
            accessible_classes.order_by("-annee_scolaire")
            .values_list("annee_scolaire", flat=True)
            .first()
            or ""
        )

    status = (request.GET.get("statut") or "VALIDE").strip().upper()
    status_labels = dict(Paiement.STATUT_CHOICES)
    if status not in status_labels and status != "TOUS":
        status = "VALIDE"
    mode_value = (request.GET.get("mode_id") or "").strip()
    selected_mode_id = int(mode_value) if mode_value.isdigit() else None
    if selected_mode_id and not ModePaiement.objects.filter(
        pk=selected_mode_id
    ).exists():
        selected_mode_id = None
    situation_filter = (request.GET.get("situation") or "").strip()
    if situation_filter not in {"", "solde", "reste", "sans_echeancier"}:
        situation_filter = ""
    search = (request.GET.get("q") or "").strip()

    payments = filter_by_user_school(
        Paiement.objects.select_related(
            "eleve", "eleve__classe", "eleve__classe__ecole", "mode_paiement"
        ),
        request.user,
        "eleve__classe__ecole",
    ).filter(date_paiement__range=(start, end))
    if selected_school_id:
        payments = payments.filter(eleve__classe__ecole_id=selected_school_id)
    if selected_year:
        payments = payments.filter(annee_scolaire=selected_year)
    if selected_class:
        payments = payments.filter(eleve__classe_id=selected_class.pk)
    if status != "TOUS":
        payments = payments.filter(statut=status)
    if selected_mode_id:
        payments = payments.filter(mode_paiement_id=selected_mode_id)
    if search:
        payments = payments.filter(
            Q(eleve__nom__icontains=search)
            | Q(eleve__prenom__icontains=search)
            | Q(eleve__matricule__icontains=search)
            | Q(numero_recu__icontains=search)
            | Q(reference_externe__icontains=search)
        )

    grouped = list(
        payments.order_by()
        .values(
            "eleve_id",
            "eleve__matricule",
            "eleve__nom",
            "eleve__prenom",
            "eleve__classe_id",
            "eleve__classe__nom",
            "eleve__classe__ecole__nom",
            "annee_scolaire",
            "mode_paiement_id",
            "mode_paiement__nom",
        )
        .annotate(
            operation_count=Count("id"),
            period_amount=Sum("montant"),
            last_payment=Max("date_paiement"),
        )
        .order_by(
            "mode_paiement__nom",
            "eleve__classe__nom",
            "eleve__nom",
            "eleve__prenom",
        )
    )

    student_ids = {item["eleve_id"] for item in grouped}
    school_years = {item["annee_scolaire"] for item in grouped}
    schedules = list(
        EcheancierPaiement.objects.filter(
            eleve_id__in=student_ids, annee_scolaire__in=school_years
        ).select_related("eleve", "eleve__classe")
    )
    situations = calculer_situations_echeanciers(
        schedules, date_reference=end, date_limite=end
    )
    schedule_by_key = {
        (schedule.eleve_id, schedule.annee_scolaire): schedule
        for schedule in schedules
    }

    rows = []
    unique_situations = {}
    for item in grouped:
        key = (item["eleve_id"], item["annee_scolaire"])
        schedule = schedule_by_key.get(key)
        situation = situations.get(schedule.pk) if schedule else None
        label, situation_code = _situation_label(situation)
        if situation_filter and situation_code != situation_filter:
            continue
        if situation:
            unique_situations[key] = situation
        row = {
            "student_id": item["eleve_id"],
            "matricule": item["eleve__matricule"],
            "student": " ".join(
                filter(None, [item["eleve__nom"], item["eleve__prenom"]])
            ),
            "school": item["eleve__classe__ecole__nom"],
            "class": item["eleve__classe__nom"],
            "school_year": item["annee_scolaire"],
            "mode_id": item["mode_paiement_id"],
            "mode": item["mode_paiement__nom"] or "Non précisé",
            "operation_count": item["operation_count"],
            "period_amount": item["period_amount"] or ZERO,
            "last_payment": item["last_payment"],
            "total_due": situation["total_du"] if situation else None,
            "paid": situation["encaisse"] if situation else None,
            "discount": situation["remises"] if situation else None,
            "remaining": situation["reste"] if situation else None,
            "situation": label,
            "situation_code": situation_code,
        }
        rows.append(row)

    mode_summary = defaultdict(
        lambda: {"amount": ZERO, "operations": 0, "students": set()}
    )
    for row in rows:
        summary = mode_summary[row["mode"]]
        summary["amount"] += row["period_amount"]
        summary["operations"] += row["operation_count"]
        summary["students"].add(row["student_id"])
    mode_totals = [
        {
            "name": name,
            "amount": values["amount"],
            "operations": values["operations"],
            "students": len(values["students"]),
        }
        for name, values in sorted(
            mode_summary.items(), key=lambda item: (-item[1]["amount"], item[0])
        )
    ]

    student_keys = {
        (row["student_id"], row["school_year"]) for row in rows
    }
    relevant_situations = {
        key: unique_situations[key]
        for key in student_keys
        if key in unique_situations
    }
    paginator = Paginator(rows, 50)
    page_obj = paginator.get_page(request.GET.get("page") or 1)
    query = request.GET.copy()
    query.pop("page", None)
    query.pop("fragment", None)
    options = _filter_options(request, selected_school_id, selected_year)
    selected_school = next(
        (school for school in options["schools"] if school.pk == selected_school_id),
        None,
    )
    return {
        "titre_page": "Élèves et soldes par mode d'encaissement",
        "date_debut": start,
        "date_fin": end,
        "statut": status,
        "status_label": "Tous les statuts" if status == "TOUS" else status_labels[status],
        "q": search,
        "situation_filter": situation_filter,
        "selected_mode_id": selected_mode_id,
        "selected_school_id": selected_school_id,
        "selected_school": selected_school,
        "selected_class_id": selected_class.pk if selected_class else None,
        "selected_year": selected_year,
        "page_obj": page_obj,
        "rows": page_obj.object_list,
        "mode_totals": mode_totals,
        "query_string": query.urlencode(),
        "total_amount": sum((row["period_amount"] for row in rows), ZERO),
        "operation_count": sum(row["operation_count"] for row in rows),
        "student_count": len(student_keys),
        "settled_count": sum(
            1 for situation in relevant_situations.values()
            if situation["total_du"] > 0 and situation["reste"] <= 0
        ),
        "remaining_total": sum(
            (situation["reste"] for situation in relevant_situations.values()), ZERO
        ),
        **options,
    }


@can_view_reports
def payment_modes_students(request):
    context = _payment_modes_detail_data(request)
    if request.GET.get("fragment") == "1":
        return render(request, "paiements/_modes_encaissement_resultats.html", context)
    return render(request, "paiements/modes_encaissement_detail.html", context)
