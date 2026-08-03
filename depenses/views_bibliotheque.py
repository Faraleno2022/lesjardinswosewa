import re

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import datetime, date, timedelta
from decimal import Decimal

from .models_bibliotheque import (
    CategorieLivre, Livre, Emprunt, Reservation,
    HistoriqueLivre, ParametreBibliotheque
)
from .forms import ReservationForm
from eleves.models import Eleve
from utilisateurs.utils import user_is_superadmin, user_school


STATUTS_RESERVATION_ACTIFS = ('EN_ATTENTE', 'DISPONIBLE')


def _livres_bibliotheque_pour_user(user):
    """Livres visibles par l'utilisateur courant."""
    livres = Livre.objects.filter(actif=True)
    if user_is_superadmin(user):
        return livres
    ecole = user_school(user)
    if ecole is None:
        return livres.none()
    return livres.filter(cree_par__profil__ecole=ecole)


def _eleves_bibliotheque_pour_user(user):
    """Élèves actifs de l'école de l'utilisateur courant."""
    eleves = Eleve.objects.filter(statut='ACTIF').select_related(
        'classe', 'classe__ecole'
    )
    if user_is_superadmin(user):
        return eleves
    ecole = user_school(user)
    if ecole is None:
        return eleves.none()
    return eleves.filter(classe__ecole=ecole)


def _reservations_bibliotheque_pour_user(user):
    """Réservations de l'école, rattachées par la classe de l'élève."""
    reservations = Reservation.objects.select_related(
        'livre', 'eleve', 'eleve__classe', 'eleve__classe__ecole', 'cree_par'
    )
    if user_is_superadmin(user):
        return reservations
    ecole = user_school(user)
    if ecole is None:
        return reservations.none()
    return reservations.filter(eleve__classe__ecole=ecole)


def _parametres_bibliotheque():
    """Retourne les paramètres enregistrés ou les valeurs par défaut du modèle."""
    return ParametreBibliotheque.objects.first() or ParametreBibliotheque()


def _expirer_reservations(queryset=None):
    """Expire les réservations actives dont la date limite est dépassée."""
    reservations = queryset if queryset is not None else Reservation.objects.all()
    expirees = list(reservations.filter(
        statut__in=STATUTS_RESERVATION_ACTIFS,
        date_expiration__lt=timezone.now(),
    ))
    for reservation in expirees:
        reservation.statut = 'EXPIREE'
        reservation.save()
    return len(expirees)


def _prochain_numero_reservation():
    """Génère un numéro journalier lisible : RES-AAAAMMJJ-0001."""
    prefixe = f"RES-{timezone.localdate().strftime('%Y%m%d')}"
    derniere = Reservation.objects.select_for_update().filter(
        numero_reservation__startswith=prefixe
    ).order_by('-numero_reservation').first()
    sequence = 0
    if derniere:
        try:
            sequence = int(derniere.numero_reservation.rsplit('-', 1)[-1])
        except (TypeError, ValueError):
            sequence = 0
    return f'{prefixe}-{sequence + 1:04d}'


def _promouvoir_reservations_en_attente(livre):
    """Rend disponibles les premières réservations selon le stock libéré."""
    _expirer_reservations(Reservation.objects.filter(livre=livre))
    maintenant = timezone.now()
    deja_disponibles = Reservation.objects.filter(
        livre=livre,
        statut='DISPONIBLE',
        date_expiration__gte=maintenant,
    ).count()
    places = max(0, livre.exemplaires_disponibles - deja_disponibles)
    if places == 0:
        return []

    params = _parametres_bibliotheque()
    duree = max(1, params.duree_reservation_defaut)
    reservations = list(
        Reservation.objects.select_for_update().filter(
            livre=livre,
            statut='EN_ATTENTE',
            date_expiration__gte=maintenant,
        ).order_by('date_reservation')[:places]
    )
    for reservation in reservations:
        reservation.statut = 'DISPONIBLE'
        reservation.date_notification = maintenant
        reservation.date_expiration = maintenant + timedelta(days=duree)
        reservation.save()
    return reservations


@login_required
def dashboard_bibliotheque(request):
    """Dashboard principal de la bibliothèque"""
    from utilisateurs.utils import user_school

    ecole = user_school(request.user)

    # Filtres de base par école
    livres_qs = Livre.objects.filter(actif=True)
    emprunts_qs = Emprunt.objects.all()
    reservations_qs = Reservation.objects.all()
    if ecole:
        livres_qs = livres_qs.filter(cree_par__profil__ecole=ecole)
        emprunts_qs = emprunts_qs.filter(cree_par__profil__ecole=ecole)
        reservations_qs = reservations_qs.filter(eleve__classe__ecole=ecole)

    _expirer_reservations(reservations_qs)

    # Statistiques générales
    total_livres = livres_qs.count()
    total_exemplaires = livres_qs.aggregate(
        total=Sum('nombre_exemplaires')
    )['total'] or 0

    livres_disponibles = livres_qs.filter(
        statut='DISPONIBLE',
        exemplaires_disponibles__gt=0
    ).count()

    # Emprunts
    emprunts_en_cours = emprunts_qs.filter(statut='EN_COURS').count()
    emprunts_en_retard = emprunts_qs.filter(statut='EN_RETARD').count()

    # Réservations
    reservations_actives = reservations_qs.filter(
        statut__in=['EN_ATTENTE', 'DISPONIBLE']
    ).count()

    # Pénalités à recouvrer
    penalites_total = emprunts_qs.filter(
        penalite_payee=False,
        montant_penalite__gt=0
    ).aggregate(total=Sum('montant_penalite'))['total'] or 0

    # Derniers emprunts
    derniers_emprunts = emprunts_qs.select_related(
        'livre', 'eleve', 'cree_par'
    ).order_by('-date_emprunt')[:10]

    # Livres les plus empruntés
    livres_populaires = livres_qs.annotate(
        nb_emprunts=Count('emprunts')
    ).order_by('-nb_emprunts')[:10]

    # Répartition par catégorie
    repartition_categories = CategorieLivre.objects.annotate(
        nb_livres=Count('livres')
    ).filter(actif=True)
    
    context = {
        'titre_page': 'Dashboard Bibliothèque',
        'total_livres': total_livres,
        'total_exemplaires': total_exemplaires,
        'livres_disponibles': livres_disponibles,
        'emprunts_en_cours': emprunts_en_cours,
        'emprunts_en_retard': emprunts_en_retard,
        'reservations_actives': reservations_actives,
        'penalites_total': penalites_total,
        'derniers_emprunts': derniers_emprunts,
        'livres_populaires': livres_populaires,
        'repartition_categories': repartition_categories,
    }
    
    return render(request, 'depenses/bibliotheque/dashboard.html', context)


@login_required
def catalogue_livres(request):
    """Catalogue des livres"""
    from utilisateurs.utils import user_school

    # Filtres
    q = request.GET.get('q', '')
    categorie_id = request.GET.get('categorie', '')
    statut = request.GET.get('statut', '')
    langue = request.GET.get('langue', '')

    livres = Livre.objects.select_related('categorie').filter(actif=True)
    # Sécurité : filtrer par école
    ecole = user_school(request.user)
    if ecole:
        livres = livres.filter(cree_par__profil__ecole=ecole)
    
    if q:
        livres = livres.filter(
            Q(code_livre__icontains=q) |
            Q(isbn__icontains=q) |
            Q(titre__icontains=q) |
            Q(auteur__icontains=q) |
            Q(editeur__icontains=q) |
            Q(mots_cles__icontains=q)
        )
    
    if categorie_id:
        livres = livres.filter(categorie_id=categorie_id)
    
    if statut:
        livres = livres.filter(statut=statut)
    
    if langue:
        livres = livres.filter(langue=langue)
    
    categories = CategorieLivre.objects.filter(actif=True)
    
    context = {
        'titre_page': 'Catalogue de Livres',
        'livres': livres,
        'categories': categories,
        'q': q,
        'categorie_id': categorie_id,
        'statut': statut,
        'langue': langue,
    }
    
    return render(request, 'depenses/bibliotheque/catalogue.html', context)


@login_required
def liste_emprunts(request):
    """Liste des emprunts"""
    from utilisateurs.utils import user_school

    # Filtres
    statut = request.GET.get('statut', '')
    eleve_id = request.GET.get('eleve', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')

    emprunts = Emprunt.objects.select_related(
        'livre', 'eleve', 'eleve__classe', 'cree_par'
    ).all()
    # Sécurité : filtrer par école
    ecole = user_school(request.user)
    if ecole:
        emprunts = emprunts.filter(cree_par__profil__ecole=ecole)
    
    if statut:
        emprunts = emprunts.filter(statut=statut)
    
    if eleve_id:
        emprunts = emprunts.filter(eleve_id=eleve_id)
    
    if date_debut:
        emprunts = emprunts.filter(date_emprunt__gte=date_debut)
    
    if date_fin:
        emprunts = emprunts.filter(date_emprunt__lte=date_fin)
    
    context = {
        'titre_page': 'Emprunts',
        'emprunts': emprunts,
        'statut': statut,
        'eleve_id': eleve_id,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }
    
    return render(request, 'depenses/bibliotheque/liste_emprunts.html', context)


@login_required
def creer_emprunt(request):
    """Créer un emprunt en respectant la priorité des réservations."""

    if request.method == 'POST':
        livre_id = request.POST.get('livre')
        eleve_id = request.POST.get('eleve')
        reservation_id = request.POST.get('reservation') or None
        try:
            duree_jours = int(request.POST.get('duree_jours', 14))
        except (ValueError, TypeError):
            duree_jours = 14
        duree_jours = max(1, duree_jours)

        livre = get_object_or_404(
            _livres_bibliotheque_pour_user(request.user), pk=livre_id
        )
        eleve = get_object_or_404(
            _eleves_bibliotheque_pour_user(request.user), pk=eleve_id
        )

        # Vérifier le nombre d'emprunts de l'élève
        params = _parametres_bibliotheque()
        emprunts_actifs = Emprunt.objects.filter(
            eleve=eleve,
            statut__in=['EN_COURS', 'EN_RETARD'],
        ).count()
        if emprunts_actifs >= params.nombre_emprunts_max:
            messages.error(
                request,
                f"L'élève a déjà atteint le nombre maximum d'emprunts "
                f"({params.nombre_emprunts_max})."
            )
            return redirect('depenses:creer_emprunt')

        with transaction.atomic():
            # Verrouiller le livre pour éviter la race condition sur les exemplaires
            livre_locked = Livre.objects.select_for_update().get(pk=livre.pk)
            _expirer_reservations(Reservation.objects.filter(livre=livre_locked))
            _promouvoir_reservations_en_attente(livre_locked)

            if reservation_id:
                reservation = get_object_or_404(
                    _reservations_bibliotheque_pour_user(
                        request.user
                    ).select_for_update(),
                    pk=reservation_id,
                    livre=livre_locked,
                    eleve=eleve,
                )
                if reservation.statut != 'DISPONIBLE':
                    messages.error(
                        request,
                        "Cette réservation n'est pas disponible pour un emprunt."
                    )
                    return redirect('depenses:liste_reservations')
            else:
                reservation = Reservation.objects.select_for_update().filter(
                    livre=livre_locked,
                    eleve=eleve,
                    statut='DISPONIBLE',
                    date_expiration__gte=timezone.now(),
                ).order_by('date_reservation').first()

            reservations_prioritaires = Reservation.objects.filter(
                livre=livre_locked,
                statut='DISPONIBLE',
                date_expiration__gte=timezone.now(),
            )
            if reservations_prioritaires.exists() and (
                reservation is None or reservation.statut != 'DISPONIBLE'
            ):
                messages.error(
                    request,
                    "Ce livre est réservé pour un autre élève. Traitez d'abord "
                    "la réservation prioritaire."
                )
                return redirect('depenses:liste_reservations')

            # Vérifier la disponibilité (après verrouillage)
            if not livre_locked.est_disponible:
                messages.error(request, "Ce livre n'est pas disponible.")
                return redirect('depenses:creer_emprunt')

            # Créer l'emprunt
            today = date.today()
            prefix = f"EMP-{today.strftime('%Y%m%d')}"
            last_emp = Emprunt.objects.filter(
                numero_emprunt__startswith=prefix
            ).order_by('-numero_emprunt').first()

            if last_emp:
                last_num = int(last_emp.numero_emprunt.split('-')[-1])
                numero_emprunt = f"{prefix}-{last_num + 1:04d}"
            else:
                numero_emprunt = f"{prefix}-0001"

            emprunt = Emprunt.objects.create(
                numero_emprunt=numero_emprunt,
                livre=livre_locked,
                eleve=eleve,
                date_emprunt=today,
                date_retour_prevue=today + timedelta(days=duree_jours),
                etat_livre_emprunt=livre_locked.etat,
                cree_par=request.user
            )

            # Mettre à jour le livre
            livre_locked.exemplaires_disponibles -= 1
            if livre_locked.exemplaires_disponibles == 0:
                livre_locked.statut = 'EMPRUNTE'
            livre_locked.save()

            if reservation is not None:
                reservation.statut = 'EMPRUNTEE'
                reservation.save()

            # Si plusieurs exemplaires restent disponibles, servir la file suivante.
            _promouvoir_reservations_en_attente(livre_locked)

            # Historique
            HistoriqueLivre.objects.create(
                livre=livre_locked,
                action='EMPRUNT',
                description=f'Emprunté par {eleve} - {numero_emprunt}',
                utilisateur=request.user
            )

        messages.success(request, f'Emprunt créé avec succès. N° {numero_emprunt}')
        return redirect('depenses:liste_emprunts')

    livres = _livres_bibliotheque_pour_user(request.user).filter(
        statut='DISPONIBLE', exemplaires_disponibles__gt=0
    ).order_by('titre')
    eleves = _eleves_bibliotheque_pour_user(request.user).order_by(
        'nom', 'prenom'
    )
    params = _parametres_bibliotheque()

    context = {
        'titre_page': 'Nouvel Emprunt',
        'livres': livres,
        'eleves': eleves,
        'params': params,
        'selected_livre_id': request.GET.get('livre', ''),
        'selected_eleve_id': request.GET.get('eleve', ''),
        'reservation_id': request.GET.get('reservation', ''),
    }

    return render(request, 'depenses/bibliotheque/form_emprunt.html', context)


@login_required
def retourner_livre(request, emprunt_id):
    """Retourner un livre"""
    from utilisateurs.utils import user_school

    emprunt = get_object_or_404(
        Emprunt.objects.select_related('livre', 'eleve', 'eleve__classe', 'eleve__classe__ecole'),
        pk=emprunt_id
    )

    # Sécurité : vérifier l'appartenance à l'école
    ecole = user_school(request.user)
    if ecole and emprunt.eleve.classe and emprunt.eleve.classe.ecole != ecole:
        messages.error(request, "Accès refusé : cet emprunt n'appartient pas à votre école.")
        return redirect('depenses:liste_emprunts')

    if request.method == 'POST':
        etat_retour = request.POST.get('etat_retour')
        observations = request.POST.get('observations', '')

        reservations_promues = []
        with transaction.atomic():
            # Verrouiller l'emprunt pour éviter le double retour
            emprunt_locked = Emprunt.objects.select_for_update().get(pk=emprunt.pk)

            if emprunt_locked.statut == 'RETOURNE':
                messages.warning(request, 'Ce livre a déjà été retourné.')
                return redirect('depenses:liste_emprunts')

            # Mettre à jour l'emprunt
            emprunt_locked.date_retour_effectif = date.today()
            emprunt_locked.etat_livre_retour = etat_retour
            emprunt_locked.observations_retour = observations
            emprunt_locked.statut = 'RETOURNE'
            emprunt_locked.traite_par = request.user

            # Calculer les pénalités
            params = ParametreBibliotheque.objects.first()
            if params:
                emprunt_locked.calculer_penalite(params.penalite_retard_journalier)
            else:
                emprunt_locked.calculer_penalite()

            emprunt_locked.save()

            # Mettre à jour le livre (verrouillé aussi)
            livre = Livre.objects.select_for_update().get(pk=emprunt_locked.livre_id)
            livre.exemplaires_disponibles += 1
            livre.statut = 'DISPONIBLE'
            livre.etat = etat_retour
            livre.save()

            reservations_promues = _promouvoir_reservations_en_attente(livre)

            # Historique
            HistoriqueLivre.objects.create(
                livre=livre,
                action='RETOUR',
                description=f'Retourné par {emprunt_locked.eleve} - {emprunt_locked.numero_emprunt}',
                utilisateur=request.user
            )

        if reservations_promues:
            noms = ', '.join(
                reservation.eleve.nom_complet
                for reservation in reservations_promues
            )
            messages.info(
                request,
                f'Livre maintenant disponible pour la réservation de : {noms}.'
            )

        if emprunt_locked.montant_penalite > 0:
            messages.warning(
                request,
                f'Livre retourné. Pénalité de retard : {emprunt_locked.montant_penalite:,.0f} GNF'
            )
        else:
            messages.success(request, 'Livre retourné avec succès.')

        return redirect('depenses:liste_emprunts')

    context = {
        'titre_page': 'Retour de Livre',
        'emprunt': emprunt,
    }

    return render(request, 'depenses/bibliotheque/retour_livre.html', context)


@login_required
def liste_reservations(request):
    """Liste filtrable des réservations de l'école."""
    statut = request.GET.get('statut', '')
    recherche = (request.GET.get('q') or '').strip()

    base = _reservations_bibliotheque_pour_user(request.user)
    _expirer_reservations(base)

    stats = {
        'total': base.count(),
        'en_attente': base.filter(statut='EN_ATTENTE').count(),
        'disponibles': base.filter(statut='DISPONIBLE').count(),
        'terminees': base.filter(
            statut__in=['EMPRUNTEE', 'ANNULEE', 'EXPIREE']
        ).count(),
    }

    reservations = base.order_by('-date_reservation')
    statuts_valides = {code for code, _ in Reservation.STATUT_CHOICES}
    if statut in statuts_valides:
        reservations = reservations.filter(statut=statut)
    else:
        statut = ''

    if recherche:
        reservations = reservations.filter(
            Q(numero_reservation__icontains=recherche)
            | Q(livre__titre__icontains=recherche)
            | Q(eleve__matricule__icontains=recherche)
            | Q(eleve__nom__icontains=recherche)
            | Q(eleve__prenom__icontains=recherche)
        )

    context = {
        'titre_page': 'Réservations',
        'reservations': reservations,
        'statut': statut,
        'q': recherche,
        'stats': stats,
        'statuts_reservation': Reservation.STATUT_CHOICES,
        'params': _parametres_bibliotheque(),
    }

    return render(request, 'depenses/bibliotheque/liste_reservations.html', context)


@login_required
def creer_reservation(request):
    """Créer une réservation en appliquant les limites de la bibliothèque."""
    params = _parametres_bibliotheque()
    form = ReservationForm(
        request.POST or None,
        user=request.user,
        initial={
            'livre': request.GET.get('livre', ''),
            'eleve': request.GET.get('eleve', ''),
        },
    )

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            livre = get_object_or_404(
                _livres_bibliotheque_pour_user(request.user).select_for_update(),
                pk=form.cleaned_data['livre'].pk,
            )
            eleve = get_object_or_404(
                _eleves_bibliotheque_pour_user(request.user).select_for_update(),
                pk=form.cleaned_data['eleve'].pk,
            )
            maintenant = timezone.now()
            _expirer_reservations(Reservation.objects.filter(eleve=eleve))

            reservations_actives = Reservation.objects.filter(
                eleve=eleve,
                statut__in=STATUTS_RESERVATION_ACTIFS,
                date_expiration__gte=maintenant,
            )
            if reservations_actives.filter(livre=livre).exists():
                form.add_error(
                    'livre',
                    "Cet élève possède déjà une réservation active pour ce livre."
                )
            elif reservations_actives.count() >= params.nombre_reservations_max:
                form.add_error(
                    'eleve',
                    f"Cet élève a atteint la limite de "
                    f"{params.nombre_reservations_max} réservations actives."
                )
            else:
                deja_disponibles = Reservation.objects.filter(
                    livre=livre,
                    statut='DISPONIBLE',
                    date_expiration__gte=maintenant,
                ).count()
                est_disponible = (
                    livre.est_disponible
                    and livre.exemplaires_disponibles > deja_disponibles
                )
                duree = max(1, params.duree_reservation_defaut)
                reservation = form.save(commit=False)
                reservation.livre = livre
                reservation.eleve = eleve
                reservation.numero_reservation = _prochain_numero_reservation()
                reservation.date_reservation = maintenant
                reservation.date_expiration = maintenant + timedelta(days=duree)
                reservation.statut = 'DISPONIBLE' if est_disponible else 'EN_ATTENTE'
                reservation.date_notification = maintenant if est_disponible else None
                reservation.cree_par = request.user
                reservation.save()

                HistoriqueLivre.objects.create(
                    livre=livre,
                    action='RESERVATION',
                    description=(
                        f'Réservation par {eleve} - '
                        f'{reservation.numero_reservation}'
                    ),
                    utilisateur=request.user,
                )
                messages.success(
                    request,
                    f'Réservation créée avec succès. '
                    f'N° {reservation.numero_reservation}'
                )
                return redirect('depenses:liste_reservations')

    context = {
        'titre_page': 'Nouvelle réservation',
        'form': form,
        'params': params,
    }
    return render(request, 'depenses/bibliotheque/form_reservation.html', context)


@login_required
@require_POST
def annuler_reservation(request, reservation_id):
    """Annuler une réservation active et servir la suivante si possible."""
    reservation = get_object_or_404(
        _reservations_bibliotheque_pour_user(request.user),
        pk=reservation_id,
    )
    if reservation.statut not in STATUTS_RESERVATION_ACTIFS:
        messages.warning(request, "Cette réservation n'est plus active.")
        return redirect('depenses:liste_reservations')

    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(
            pk=reservation.pk
        )
        reservation.statut = 'ANNULEE'
        reservation.save()
        livre = Livre.objects.select_for_update().get(pk=reservation.livre_id)
        _promouvoir_reservations_en_attente(livre)
        HistoriqueLivre.objects.create(
            livre=livre,
            action='RESERVATION',
            description=(
                f'Annulation de {reservation.numero_reservation} '
                f'pour {reservation.eleve}'
            ),
            utilisateur=request.user,
        )

    messages.success(request, 'Réservation annulée avec succès.')
    return redirect('depenses:liste_reservations')


@login_required
def statistiques_bibliotheque(request):
    """Statistiques de la bibliothèque"""
    from utilisateurs.utils import user_school

    ecole = user_school(request.user)

    # Période
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')

    if not date_debut:
        date_debut = (date.today() - timedelta(days=30)).strftime('%Y-%m-%d')
    if not date_fin:
        date_fin = date.today().strftime('%Y-%m-%d')

    # Emprunts par période
    emprunts = Emprunt.objects.filter(
        date_emprunt__gte=date_debut,
        date_emprunt__lte=date_fin
    )
    # Sécurité : filtrer par école
    if ecole:
        emprunts = emprunts.filter(cree_par__profil__ecole=ecole)

    # Statistiques
    stats = {
        'total_emprunts': emprunts.count(),
        'emprunts_retournes': emprunts.filter(statut='RETOURNE').count(),
        'emprunts_en_cours': emprunts.filter(statut='EN_COURS').count(),
        'emprunts_en_retard': emprunts.filter(statut='EN_RETARD').count(),
        'total_penalites': emprunts.aggregate(total=Sum('montant_penalite'))['total'] or 0,
    }

    # Livres les plus empruntés
    livres_populaires = Livre.objects.filter(
        emprunts__date_emprunt__gte=date_debut,
        emprunts__date_emprunt__lte=date_fin
    )
    if ecole:
        livres_populaires = livres_populaires.filter(cree_par__profil__ecole=ecole)
    livres_populaires = livres_populaires.annotate(
        nb_emprunts=Count('emprunts')
    ).order_by('-nb_emprunts')[:10]

    # Élèves les plus actifs
    eleves_actifs = Eleve.objects.filter(
        emprunts_livres__date_emprunt__gte=date_debut,
        emprunts_livres__date_emprunt__lte=date_fin
    )
    if ecole:
        eleves_actifs = eleves_actifs.filter(classe__ecole=ecole)
    eleves_actifs = eleves_actifs.annotate(
        nb_emprunts=Count('emprunts_livres')
    ).order_by('-nb_emprunts')[:10]

    context = {
        'titre_page': 'Statistiques Bibliothèque',
        'date_debut': date_debut,
        'date_fin': date_fin,
        'stats': stats,
        'livres_populaires': livres_populaires,
        'eleves_actifs': eleves_actifs,
    }

    return render(request, 'depenses/bibliotheque/statistiques.html', context)


# ─── Catégories de livres ──────────────────────────────────────────────────────
@login_required
def gestion_categories_livres(request):
    """Créer et lister les catégories de livres (indispensables pour ajouter un livre)."""
    if request.method == 'POST':
        nom = (request.POST.get('nom') or '').strip()
        code = (request.POST.get('code') or '').strip().upper()
        description = (request.POST.get('description') or '').strip()

        if not nom:
            messages.error(request, "Le nom de la catégorie est obligatoire.")
        else:
            # Générer un code automatiquement s'il n'est pas fourni
            if not code:
                base = ''.join(ch for ch in nom.upper() if ch.isalnum())[:6] or 'CAT'
                code = base
                i = 1
                while CategorieLivre.objects.filter(code=code).exists():
                    i += 1
                    code = f"{base}{i}"
            if CategorieLivre.objects.filter(code=code).exists():
                messages.error(request, f"Le code « {code} » existe déjà. Choisissez-en un autre.")
            else:
                CategorieLivre.objects.create(nom=nom, code=code, description=description)
                messages.success(request, f"Catégorie « {nom} » créée avec succès.")
                return redirect('depenses:gestion_categories_livres')

    categories = CategorieLivre.objects.annotate(nb_livres=Count('livres')).order_by('nom')
    context = {
        'titre_page': 'Catégories de livres',
        'categories': categories,
    }
    return render(request, 'depenses/bibliotheque/gestion_categories.html', context)


@login_required
def modifier_categorie_livre(request, categorie_id):
    """Modifier une catégorie de livre."""
    categorie = get_object_or_404(CategorieLivre, pk=categorie_id)
    if request.method == 'POST':
        nom = (request.POST.get('nom') or '').strip()
        code = (request.POST.get('code') or '').strip().upper()
        description = (request.POST.get('description') or '').strip()
        actif = request.POST.get('actif') == 'on'

        if not nom or not code:
            messages.error(request, "Le nom et le code sont obligatoires.")
        elif CategorieLivre.objects.filter(code=code).exclude(pk=categorie.pk).exists():
            messages.error(request, f"Le code « {code} » est déjà utilisé par une autre catégorie.")
        else:
            categorie.nom = nom
            categorie.code = code
            categorie.description = description
            categorie.actif = actif
            categorie.save()
            messages.success(request, "Catégorie modifiée avec succès.")
            return redirect('depenses:gestion_categories_livres')

    return render(request, 'depenses/bibliotheque/form_categorie.html', {
        'titre_page': 'Modifier la catégorie',
        'categorie': categorie,
    })


@login_required
@require_POST
def supprimer_categorie_livre(request, categorie_id):
    """Supprimer une catégorie (refusé si des livres l'utilisent)."""
    categorie = get_object_or_404(CategorieLivre, pk=categorie_id)
    if categorie.livres.exists():
        messages.error(
            request,
            "Impossible de supprimer : des livres utilisent cette catégorie. "
            "Désactivez-la ou réaffectez les livres."
        )
    else:
        nom = categorie.nom
        categorie.delete()
        messages.success(request, f"Catégorie « {nom} » supprimée.")
    return redirect('depenses:gestion_categories_livres')


# ─── Livres (catalogue) ────────────────────────────────────────────────────────
def _next_code_livre():
    """Génère le prochain code livre séquentiel (LIV-0001, LIV-0002, ...)."""
    dernier = Livre.objects.filter(code_livre__startswith='LIV-').order_by('-code_livre').first()
    n = 0
    if dernier:
        m = re.match(r'LIV-(\d+)', dernier.code_livre)
        if m:
            n = int(m.group(1))
    return f"LIV-{n + 1:04d}"


def _form_livre(request, livre):
    """Formulaire partagé création / édition d'un livre."""
    categories = CategorieLivre.objects.filter(actif=True).order_by('nom')

    def _val(name, default=''):
        """Valeur à pré-remplir : POST si soumis, sinon le livre existant."""
        if request.method == 'POST':
            v = request.POST.get(name, default)
        elif livre is not None:
            v = getattr(livre, name, default)
        else:
            v = default
        return default if v is None else v

    def _render_form():
        if request.method == 'POST':
            categorie_sel = request.POST.get('categorie', '')
        else:
            categorie_sel = str(livre.categorie_id) if livre and livre.categorie_id else ''
        f = {
            'titre': _val('titre'), 'code_livre': _val('code_livre'),
            'auteur': _val('auteur'), 'categorie': categorie_sel,
            'isbn': _val('isbn'), 'editeur': _val('editeur'),
            'langue': _val('langue', 'Français') or 'Français',
            'annee_publication': _val('annee_publication'),
            'nombre_pages': _val('nombre_pages'),
            'resume': _val('resume'), 'mots_cles': _val('mots_cles'),
            'emplacement': _val('emplacement'),
            'nombre_exemplaires': _val('nombre_exemplaires', '1') or '1',
            'etat': _val('etat', 'BON') or 'BON',
            'prix_acquisition': _val('prix_acquisition'),
        }
        return render(request, 'depenses/bibliotheque/form_livre.html', {
            'titre_page': 'Modifier le livre' if livre else 'Ajouter un livre',
            'livre': livre, 'categories': categories,
            'etats': Livre.ETAT_CHOICES, 'f': f,
        })

    if request.method == 'POST':
        p = request.POST
        titre = (p.get('titre') or '').strip()
        auteur = (p.get('auteur') or '').strip()
        categorie_id = p.get('categorie') or ''
        categorie = CategorieLivre.objects.filter(pk=categorie_id).first() if categorie_id else None

        def _int(name, default=0):
            try:
                return int(p.get(name) or default)
            except (TypeError, ValueError):
                return default

        manquants = []
        if not titre:
            manquants.append("le titre")
        if not auteur:
            manquants.append("l'auteur")
        if not categorie:
            manquants.append("la catégorie")

        if manquants:
            messages.error(request, "Veuillez renseigner : " + ", ".join(manquants) + ".")
            return _render_form()

        code_livre = (p.get('code_livre') or '').strip().upper() or _next_code_livre()
        doublon = Livre.objects.filter(code_livre=code_livre)
        if livre:
            doublon = doublon.exclude(pk=livre.pk)
        if doublon.exists():
            messages.error(request, f"Le code « {code_livre} » existe déjà.")
            return _render_form()

        nombre_exemplaires = max(1, _int('nombre_exemplaires', 1))
        is_new = livre is None
        old_total = 0 if is_new else livre.nombre_exemplaires
        if is_new:
            livre = Livre(cree_par=request.user)

        livre.code_livre = code_livre
        livre.titre = titre
        livre.auteur = auteur
        livre.categorie = categorie
        livre.isbn = (p.get('isbn') or '').strip()
        livre.editeur = (p.get('editeur') or '').strip()
        livre.langue = (p.get('langue') or 'Français').strip() or 'Français'
        livre.annee_publication = _int('annee_publication', 0) or None
        livre.nombre_pages = _int('nombre_pages', 0) or None
        livre.emplacement = (p.get('emplacement') or '').strip() or 'Non précisé'
        livre.etat = p.get('etat') or 'BON'
        livre.resume = (p.get('resume') or '').strip()
        livre.mots_cles = (p.get('mots_cles') or '').strip()
        prix = p.get('prix_acquisition')
        try:
            livre.prix_acquisition = int(prix) if prix else None
        except (TypeError, ValueError):
            livre.prix_acquisition = None
        livre.nombre_exemplaires = nombre_exemplaires

        if is_new:
            livre.exemplaires_disponibles = nombre_exemplaires
            livre.statut = 'DISPONIBLE'
        else:
            delta = nombre_exemplaires - old_total
            livre.exemplaires_disponibles = max(0, min(nombre_exemplaires, livre.exemplaires_disponibles + delta))

        if request.FILES.get('couverture'):
            livre.couverture = request.FILES['couverture']

        livre.save()

        HistoriqueLivre.objects.create(
            livre=livre,
            action='ACQUISITION' if is_new else 'MODIFICATION',
            description=("Ajout au catalogue" if is_new else "Modification de la fiche") + f" : {livre.titre}",
            utilisateur=request.user,
        )

        messages.success(request, f"Livre « {livre.titre} » {'ajouté' if is_new else 'modifié'} avec succès.")
        return redirect('depenses:catalogue_livres')

    return _render_form()


@login_required
def creer_livre(request):
    """Ajouter un livre au catalogue."""
    if not CategorieLivre.objects.filter(actif=True).exists():
        messages.warning(request, "Créez d'abord au moins une catégorie de livre avant d'ajouter un livre.")
        return redirect('depenses:gestion_categories_livres')
    return _form_livre(request, None)


@login_required
def modifier_livre(request, livre_id):
    """Modifier la fiche d'un livre."""
    livre = get_object_or_404(Livre, pk=livre_id)
    return _form_livre(request, livre)


@login_required
@require_POST
def supprimer_livre(request, livre_id):
    """Retirer un livre du catalogue (soft delete), sauf si emprunts en cours."""
    livre = get_object_or_404(Livre, pk=livre_id)
    if livre.emprunts.filter(statut__in=['EN_COURS', 'EN_RETARD']).exists():
        messages.error(request, "Impossible de retirer ce livre : des emprunts sont en cours.")
    else:
        livre.actif = False
        livre.save(update_fields=['actif'])
        messages.success(request, f"Livre « {livre.titre} » retiré du catalogue.")
    return redirect('depenses:catalogue_livres')
