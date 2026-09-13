"""Validation et enregistrement atomique des notes et appréciations."""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from eleves.models import Eleve
from utilisateurs.utils import user_school
from .classes_utils import trouver_classe_eleve
from .calculs_moyennes import detecter_niveau_scolaire
from .models import AppreciationMaternelle, CompositionNote, Evaluation, MatiereNote, NoteMensuelle
from .utils_rangs import invalider_cache_rangs

MOIS = {"OCTOBRE", "NOVEMBRE", "DECEMBRE", "JANVIER", "FEVRIER", "MARS", "AVRIL", "MAI", "JUIN"}
COMPOSITIONS = {"composition1": "TRIMESTRE_1", "composition2": "TRIMESTRE_2", "composition3": "TRIMESTRE_3"}

TRIMESTRES = {f"trimestre{i}": f"TRIMESTRE_{i}" for i in range(1, 4)}


def verifier_cible_saisie(user, matiere, eleve=None, annee_scolaire=None):
    if not user.is_superuser:
        ecole = user_school(user)
        if ecole is None or matiere.classe.ecole_id != ecole.pk:
            raise PermissionDenied("Accès non autorisé à cette matière.")
        if eleve is not None and (not eleve.classe_id or eleve.classe.ecole_id != ecole.pk):
            raise PermissionDenied("Accès non autorisé à cet élève.")
    if eleve is not None:
        classe = trouver_classe_eleve(matiere.classe)
        if classe is None or eleve.classe_id != classe.pk:
            raise ValidationError("L'élève ne fait pas partie de la classe de cette matière.")
    if annee_scolaire and annee_scolaire != matiere.classe.annee_scolaire:
        raise ValidationError("L'année scolaire ne correspond pas à celle de la classe.")
    return matiere.classe.annee_scolaire


def _notes_validees(donnees, cles, maximum, normaliser=False):
    if not isinstance(donnees, dict):
        raise ValidationError("Le format des notes est invalide.")
    lignes = []
    for cle, valeur in donnees.items():
        cle = cle.upper() if normaliser else cle
        if cle not in cles:
            raise ValidationError("Période de saisie inconnue.")
        absent = valeur.get("absent", False) if isinstance(valeur, dict) else False
        note = valeur.get("note") if isinstance(valeur, dict) else valeur
        if not isinstance(absent, bool):
            raise ValidationError("Le statut d'absence est invalide.")
        if not absent and note in (None, ""):
            continue
        try:
            montant = Decimal("0") if absent else Decimal(str(note).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError("Le format de la note est invalide.")
        if not montant.is_finite() or not 0 <= montant <= maximum:
            raise ValidationError(f"Note invalide : elle doit être entre 0 et {maximum}.")
        lignes.append((cle, montant, absent))
    return lignes


def enregistrer_notes_guineennes(user, data):
    if not isinstance(data, dict) or not data.get("eleve_id") or not data.get("matiere_id"):
        raise ValidationError("Élève et matière requis.")
    eleve = Eleve.objects.select_related("classe").get(pk=_identifiant(data["eleve_id"]))
    matiere = MatiereNote.objects.select_related("classe").get(pk=_identifiant(data["matiere_id"]))
    annee = verifier_cible_saisie(user, matiere, eleve, data.get("annee_scolaire"))
    maximum = Decimal("10") if detecter_niveau_scolaire(matiere.classe.nom) == "PRIMAIRE" else Decimal("20")
    mensuelles = _notes_validees(data.get("notes_mois", {}), MOIS, maximum, normaliser=True)
    compositions = _notes_validees(data.get("compositions", {}), COMPOSITIONS, maximum)
    creees = modifiees = 0
    # Toute la requete est validee avant la premiere ecriture.
    with transaction.atomic():
        for model, lignes, champ in ((NoteMensuelle, mensuelles, "mois"), (CompositionNote, compositions, "periode")):
            for periode, note, absent in lignes:
                cible = periode if champ == "mois" else COMPOSITIONS[periode]
                _, created = model.objects.update_or_create(
                    eleve=eleve, matiere=matiere, annee_scolaire=annee,
                    **{champ: cible}, defaults={"note": note, "absent": absent},
                )
                creees += int(created)
                modifiees += int(not created)
    if creees or modifiees:
        invalider_cache_rangs(matiere.classe)
    return {"success": True, "saved": creees, "updated": modifiees,
            "message": f"{creees} note(s) créée(s), {modifiees} mise(s) à jour"}


def _identifiant(valeur):
    # Django peut afficher les identifiants avec des espaces de milliers.
    texte = "".join(str(valeur).split())
    if not texte.isdecimal() or int(texte) <= 0:
        raise ValidationError("Identifiant invalide.")
    return int(texte)


def _appreciation_validee(donnees):
    if not isinstance(donnees, dict):
        raise ValidationError("Le format des appréciations est invalide.")
    absent = donnees.get("absent", False)
    appreciation = donnees.get("appreciation", "")
    commentaire = donnees.get("commentaire", "")
    if not isinstance(absent, bool):
        raise ValidationError("Le statut d'absence est invalide.")
    if not isinstance(appreciation, str) or not isinstance(commentaire, str):
        raise ValidationError("Le format des appréciations est invalide.")
    appreciation = appreciation.strip()
    if appreciation and appreciation not in dict(AppreciationMaternelle.APPRECIATION_CHOICES):
        raise ValidationError("Appréciation inconnue.")
    return {"appreciation": "" if absent else appreciation,
            "commentaire": commentaire.strip(), "absent": absent}


def enregistrer_notes_en_lot(user, data):
    """Valide le lot entier, puis écrit dans une seule transaction."""
    if not isinstance(data, dict) or not data.get("matiere_id"):
        raise ValidationError("Matière et période requises.")
    notes = data.get("notes", [])
    periode = data.get("periode")
    if not isinstance(notes, list) or any(not isinstance(ligne, dict) for ligne in notes):
        raise ValidationError("Le format des notes est invalide.")
    if not isinstance(periode, str) or periode.upper() not in dict(Evaluation.PERIODE_CHOICES):
        raise ValidationError("Période de saisie inconnue.")
    periode = periode.upper()
    matiere = MatiereNote.objects.select_related("classe").get(pk=_identifiant(data["matiere_id"]))
    annee = verifier_cible_saisie(user, matiere, annee_scolaire=data.get("annee_scolaire"))
    maximum = Decimal("10") if matiere.classe.niveau_enseignement == "PRIMAIRE" else Decimal("20")
    evaluation = None
    if data.get("evaluation_id"):
        evaluation = Evaluation.objects.get(
            pk=_identifiant(data["evaluation_id"]), matiere=matiere, periode=periode,
        )
    lignes = []
    for ligne in notes:
        eleve = Eleve.objects.select_related("classe").get(pk=_identifiant(ligne.get("eleve_id")))
        verifier_cible_saisie(user, matiere, eleve)
        if "appreciation" in ligne:
            if periode not in TRIMESTRES.values():
                raise ValidationError("Un trimestre est requis pour les appréciations.")
            valeurs = _appreciation_validee(ligne)
            if not valeurs["appreciation"] and not valeurs["absent"]:
                continue
            model, filtre = AppreciationMaternelle, {"trimestre": periode}
        else:
            notes_validees = _notes_validees({periode: ligne}, {periode}, maximum)
            if not notes_validees:
                continue
            _, note, absent = notes_validees[0]
            valeurs = {"note": note, "absent": absent}
            if periode in MOIS:
                model, filtre = NoteMensuelle, {"mois": periode}
            else:
                model, filtre = CompositionNote, {"periode": periode}
        lignes.append((eleve, model, filtre, valeurs))

    details = []
    with transaction.atomic():
        # Conserver l'évaluation utilisée par la page sans en créer lors d'un refus.
        if evaluation is None and any(model is not AppreciationMaternelle for _, model, _, _ in lignes):
            evaluation = Evaluation.objects.filter(matiere=matiere, periode=periode).first()
            if evaluation is None:
                evaluation = Evaluation.objects.create(
                    matiere=matiere, periode=periode,
                    titre=f"Note {periode.replace('_', ' ')} - {matiere.nom}",
                    type_evaluation="DEVOIR" if periode in MOIS else "COMPOSITION",
                    date_evaluation=timezone.now().date(), note_sur=maximum,
                    coefficient=matiere.coefficient if matiere.coefficient is not None else 1,
                    cree_par=user,
                )
        for eleve, model, filtre, valeurs in lignes:
            obj, created = model.objects.update_or_create(
                eleve=eleve, matiere=matiere, annee_scolaire=annee, **filtre,
                defaults={**valeurs, "cree_par": user},
            )
            appreciation = model is AppreciationMaternelle
            details.append({
                "eleve_id": eleve.pk, "eleve_nom": f"{eleve.nom} {eleve.prenom}",
                "absent": obj.absent, "created": created,
                "note": None if appreciation or obj.note is None else float(obj.note),
                "appreciation": obj.appreciation if appreciation else None,
            })
    if details:
        invalider_cache_rangs(matiere.classe)
    creees = sum(detail["created"] for detail in details)
    return {"success": True, "notes_sauvegardees": creees,
            "notes_modifiees": len(details) - creees, "total": len(details),
            "message": f"{len(details)} note(s) sauvegardée(s)", "notes_details": details,
            "evaluation_id": evaluation.pk if evaluation else None}


def enregistrer_appreciations(user, data):
    """Accepte un lot ou les trois trimestres d'un élève, sans saisie partielle."""
    if not isinstance(data, dict):
        raise ValidationError("Le format des appréciations est invalide.")
    appreciations = data.get("appreciations", {})
    if isinstance(appreciations, list):
        donnees = appreciations
    elif isinstance(appreciations, dict):
        donnees = []
        for trimestre, valeur in appreciations.items():
            if trimestre not in TRIMESTRES or not isinstance(valeur, dict):
                raise ValidationError("Trimestre ou appréciation invalide.")
            donnees.append({**valeur, "eleve_id": data.get("eleve_id"),
                            "matiere_id": data.get("matiere_id"),
                            "trimestre": TRIMESTRES[trimestre]})
    else:
        raise ValidationError("Le format des appréciations est invalide.")
    if not donnees:
        raise ValidationError("Aucune appréciation à sauvegarder.")

    lignes = []
    classes = {}
    for ligne in donnees:
        if not isinstance(ligne, dict):
            raise ValidationError("Le format des appréciations est invalide.")
        eleve = Eleve.objects.select_related("classe").get(pk=_identifiant(ligne.get("eleve_id")))
        matiere = MatiereNote.objects.select_related("classe").get(pk=_identifiant(ligne.get("matiere_id")))
        annee = verifier_cible_saisie(user, matiere, eleve, data.get("annee_scolaire"))
        verifier_cible_saisie(user, matiere, annee_scolaire=ligne.get("annee_scolaire"))
        trimestre = ligne.get("trimestre")
        if trimestre not in TRIMESTRES.values():
            raise ValidationError("Trimestre inconnu.")
        lignes.append((eleve, matiere, annee, trimestre, _appreciation_validee(ligne)))
        classes[matiere.classe_id] = matiere.classe
    with transaction.atomic():
        for eleve, matiere, annee, trimestre, valeurs in lignes:
            AppreciationMaternelle.objects.update_or_create(
                eleve=eleve, matiere=matiere, annee_scolaire=annee, trimestre=trimestre,
                defaults={**valeurs, "cree_par": user},
            )
    for classe in classes.values():
        invalider_cache_rangs(classe)
    return {"success": True, "message": f"{len(lignes)} appréciation(s) sauvegardée(s) avec succès"}
