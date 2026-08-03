"""Vues du tableau de bord et des ventes de fournitures scolaires."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    Q,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from eleves.models import Ecole
from utilisateurs.permissions import (
    can_add_expenses,
    can_delete_expenses,
    can_modify_expenses,
)
from utilisateurs.utils import user_is_superadmin, user_school

from .forms_fournitures import ProduitFournitureForm, VenteFournitureForm
from .models_fournitures import ProduitFourniture, VenteFourniture


MONEY_FIELD = DecimalField(max_digits=15, decimal_places=0)


def _ecole_utilisateur(user):
    if user_is_superadmin(user):
        return None
    return user_school(user)


def _produits_visibles(user):
    produits = ProduitFourniture.objects.select_related("ecole", "cree_par")
    if user_is_superadmin(user):
        return produits
    ecole = user_school(user)
    if ecole is None:
        return produits.none()
    return produits.filter(ecole=ecole)


def _ventes_visibles(user):
    ventes = VenteFourniture.objects.select_related("produit", "produit__ecole", "cree_par")
    if user_is_superadmin(user):
        return ventes
    ecole = user_school(user)
    if ecole is None:
        return ventes.none()
    return ventes.filter(produit__ecole=ecole)


def _produits_avec_totaux(queryset):
    chiffre_affaires_expr = ExpressionWrapper(
        F("ventes__quantite") * F("ventes__prix_vente_unitaire"),
        output_field=MONEY_FIELD,
    )
    cout_ventes_expr = ExpressionWrapper(
        F("ventes__quantite") * F("ventes__prix_achat_unitaire"),
        output_field=MONEY_FIELD,
    )
    return queryset.annotate(
        _quantite_vendue=Coalesce(
            Sum("ventes__quantite"),
            Value(0),
            output_field=IntegerField(),
        ),
        _chiffre_affaires=Coalesce(
            Sum(chiffre_affaires_expr),
            Value(Decimal("0"), output_field=MONEY_FIELD),
            output_field=MONEY_FIELD,
        ),
        _cout_ventes=Coalesce(
            Sum(cout_ventes_expr),
            Value(Decimal("0"), output_field=MONEY_FIELD),
            output_field=MONEY_FIELD,
        ),
    ).annotate(
        _solde=ExpressionWrapper(
            F("_chiffre_affaires") - F("_cout_ventes"),
            output_field=MONEY_FIELD,
        )
    )


@login_required
def tableau_bord_fournitures(request):
    produits = _produits_visibles(request.user)
    ecole_filtre = (request.GET.get("ecole") or "").strip()
    if user_is_superadmin(request.user) and ecole_filtre.isdigit():
        produits = produits.filter(ecole_id=int(ecole_filtre))

    recherche = (request.GET.get("q") or "").strip()
    if recherche:
        produits = produits.filter(
            Q(nom__icontains=recherche)
            | Q(code_produit__icontains=recherche)
            | Q(description__icontains=recherche)
        )

    produits_liste = list(_produits_avec_totaux(produits).order_by("nom"))
    produits_alerte = [
        produit for produit in produits_liste if produit.actif and produit.stock_en_alerte
    ]

    resume = {
        "nombre_produits": len(produits_liste),
        "quantite_stock": sum(produit.quantite_stock for produit in produits_liste),
        "quantite_vendue": sum(produit.quantite_vendue for produit in produits_liste),
        "quantite_restante": sum(produit.quantite_restante for produit in produits_liste),
        "chiffre_affaires": sum(
            (produit.chiffre_affaires for produit in produits_liste), Decimal("0")
        ),
        "solde": sum((produit.solde for produit in produits_liste), Decimal("0")),
        "valeur_stock": sum(
            (produit.valeur_stock_restant for produit in produits_liste), Decimal("0")
        ),
    }

    ventes = _ventes_visibles(request.user)
    if user_is_superadmin(request.user) and ecole_filtre.isdigit():
        ventes = ventes.filter(produit__ecole_id=int(ecole_filtre))

    context = {
        "titre_page": "Gestion et vente des fournitures scolaires",
        "produits": produits_liste,
        "produits_alerte": produits_alerte,
        "resume": resume,
        "ventes_recentes": ventes.order_by("-date_vente", "-date_creation")[:12],
        "recherche": recherche,
        "ecole_filtre": ecole_filtre,
        "ecoles": Ecole.objects.order_by("nom") if user_is_superadmin(request.user) else None,
    }
    return render(request, "depenses/fournitures/tableau_bord.html", context)


@login_required
@can_add_expenses
def creer_produit_fourniture(request):
    ecole = _ecole_utilisateur(request.user)
    form = ProduitFournitureForm(request.POST or None, ecole=ecole)
    if request.method == "POST" and form.is_valid():
        produit = form.save(commit=False)
        if ecole is not None:
            produit.ecole = ecole
        produit.cree_par = request.user
        produit.save()
        messages.success(request, f"Le produit « {produit.nom} » a été ajouté.")
        return redirect("depenses:tableau_bord_fournitures")

    return render(
        request,
        "depenses/fournitures/form_produit.html",
        {"form": form, "titre_page": "Ajouter un produit"},
    )


@login_required
@can_modify_expenses
def modifier_produit_fourniture(request, produit_id):
    produit = get_object_or_404(_produits_visibles(request.user), pk=produit_id)
    form = ProduitFournitureForm(
        request.POST or None,
        instance=produit,
        ecole=_ecole_utilisateur(request.user),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"Le produit « {produit.nom} » a été modifié.")
        return redirect("depenses:tableau_bord_fournitures")

    return render(
        request,
        "depenses/fournitures/form_produit.html",
        {"form": form, "produit": produit, "titre_page": "Modifier le produit"},
    )


@login_required
@can_add_expenses
def enregistrer_vente_fourniture(request, produit_id):
    produit = get_object_or_404(_produits_visibles(request.user), pk=produit_id, actif=True)
    form = VenteFournitureForm(request.POST or None, produit=produit)

    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            try:
                produit_verrouille = _produits_visibles(request.user).select_for_update().get(
                    pk=produit_id,
                    actif=True,
                )
            except ProduitFourniture.DoesNotExist as exc:
                raise Http404 from exc

            deja_vendu = produit_verrouille.ventes.aggregate(total=Sum("quantite"))["total"] or 0
            disponible = max(0, produit_verrouille.quantite_stock - deja_vendu)
            quantite = form.cleaned_data["quantite"]
            if quantite > disponible:
                form.add_error(
                    "quantite",
                    f"Stock insuffisant : {disponible} unité(s) disponible(s).",
                )
            else:
                vente = form.save(commit=False)
                vente.produit = produit_verrouille
                vente.prix_achat_unitaire = produit_verrouille.prix_achat_unitaire
                vente.cree_par = request.user
                vente.save()
                messages.success(
                    request,
                    f"Vente enregistrée : {quantite} × {produit_verrouille.nom}.",
                )
                return redirect("depenses:tableau_bord_fournitures")

    produit.refresh_from_db()
    return render(
        request,
        "depenses/fournitures/form_vente.html",
        {"form": form, "produit": produit, "titre_page": "Enregistrer une vente"},
    )


@login_required
@can_delete_expenses
@require_POST
def supprimer_produit_fourniture(request, produit_id):
    produit = get_object_or_404(_produits_visibles(request.user), pk=produit_id)
    if produit.ventes.exists():
        messages.error(
            request,
            "Ce produit possède des ventes. Désactivez-le pour préserver l'historique.",
        )
    else:
        nom = produit.nom
        produit.delete()
        messages.success(request, f"Le produit « {nom} » a été supprimé.")
    return redirect("depenses:tableau_bord_fournitures")


@login_required
@can_delete_expenses
@require_POST
def annuler_vente_fourniture(request, vente_id):
    vente = get_object_or_404(_ventes_visibles(request.user), pk=vente_id)
    reference = vente.reference
    vente.delete()
    messages.success(request, f"La vente {reference} a été annulée et le stock recalculé.")
    return redirect("depenses:tableau_bord_fournitures")
