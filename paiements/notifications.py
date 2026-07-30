import os
from datetime import datetime
from typing import Optional

from django.utils import timezone

from .models import Paiement, Eleve, Relance
from .twilio_utils import send_message_async, send_payment_confirmation_async


def _format_amount(val) -> str:
    try:
        return f"{int(val):,}".replace(",", " ") + " GNF"
    except Exception:
        return f"{val} GNF"


def _safe_phone(number: Optional[str]) -> Optional[str]:
    if not number:
        return None
    num = number.strip()
    # Auto-prefix handled globally, but ensure +224 presence
    if not num.startswith("+") and num.isdigit():
        num = "+224" + num
    return num


# -----------------------------
# Message builders
# -----------------------------

def build_payment_receipt_message(paiement: Paiement) -> str:
    eleve = paiement.eleve
    date_txt = paiement.date_paiement.strftime("%d/%m/%Y") if isinstance(paiement.date_paiement, datetime) else paiement.date_paiement.strftime("%d/%m/%Y")
    type_nom = getattr(paiement.type_paiement, "nom", "Paiement")
    parts = [
        "Reçu de paiement",
        f"Élève: {eleve.nom_complet} ({eleve.matricule})",
        f"Type: {type_nom}",
        f"Montant: {_format_amount(paiement.montant)}",
        f"Date: {date_txt}",
    ]
    if paiement.numero_recu:
        parts.append(f"Reçu N°: {paiement.numero_recu}")
    if paiement.reference_externe:
        parts.append(f"Réf: {paiement.reference_externe}")
    parts.append("Merci pour votre confiance – myschool")
    return "\n".join(parts)


def build_enrollment_receipt_message(eleve: Eleve, paiement: Optional[Paiement] = None) -> str:
    today = timezone.localdate() if hasattr(timezone, "localdate") else datetime.today().date()
    date_txt = today.strftime("%d/%m/%Y")
    parts = [
        "Confirmation d'inscription",
        f"Élève: {eleve.nom_complet} ({eleve.matricule})",
        f"Classe: {getattr(eleve.classe, 'nom', '')}",
        f"Date: {date_txt}",
    ]
    if paiement is not None:
        parts.append(f"Frais d'inscription: {_format_amount(paiement.montant)}")
        if paiement.numero_recu:
            parts.append(f"Reçu N°: {paiement.numero_recu}")
    parts.append("Bienvenue à l'myschool")
    return "\n".join(parts)


def build_relance_message(relance: Relance) -> str:
    eleve = relance.eleve
    parts = [
        "Relance de paiement",
        f"Élève: {eleve.nom_complet} ({eleve.matricule})",
        f"Message: {relance.message}",
    ]
    if relance.solde_estime:
        parts.append(f"Solde estimé: {_format_amount(relance.solde_estime)}")
    parts.append("Merci de régulariser votre situation dans les meilleurs délais.")
    return "\n".join(parts)


def build_retard_message(eleve: Eleve, solde_restant) -> str:
    parts = [
        "Alerte: retard de paiement",
        f"Élève: {eleve.nom_complet} ({eleve.matricule})",
        f"Solde restant: {_format_amount(solde_restant)}",
        "Merci de procéder au paiement pour éviter des pénalités.",
    ]
    return "\n".join(parts)


# -----------------------------
# Send helpers
# -----------------------------

def send_payment_receipt(eleve: Eleve, paiement: Paiement) -> None:
    """Envoie le reçu de paiement par WhatsApp (par défaut) et un SMS court.
    Utilise les vars d'env TWILIO_ENABLED/TWILIO_CHANNEL.
    """
    tel = _safe_phone(getattr(eleve.responsable_principal, "telephone", None))
    if not tel:
        return
    body = build_payment_receipt_message(paiement)
    # WhatsApp (ou canal par défaut)
    send_payment_confirmation_async(to_number=tel, body=body)
    # SMS court d'information
    sms_body = (
        f"Paiement reçu pour {eleve.nom_complet}: {_format_amount(paiement.montant)}. "
        f"Reçu {paiement.numero_recu or ''}"
    ).strip()
    send_message_async(to_number=tel, body=sms_body, channel="sms")


def send_enrollment_confirmation(eleve: Eleve, paiement: Optional[Paiement] = None) -> None:
    tel = _safe_phone(getattr(eleve.responsable_principal, "telephone", None))
    if not tel:
        return
    body = build_enrollment_receipt_message(eleve, paiement=paiement)
    send_payment_confirmation_async(to_number=tel, body=body)
    sms_body = f"Inscription confirmée pour {eleve.nom_complet}. Bienvenue!"
    send_message_async(to_number=tel, body=sms_body, channel="sms")


def send_relance_notification(relance: Relance, to_number: Optional[str] = None) -> None:
    eleve = relance.eleve
    tel = _safe_phone(to_number) if to_number else _safe_phone(getattr(eleve.responsable_principal, "telephone", None))
    if not tel:
        return
    body = build_relance_message(relance)
    # Canal: respecter le choix sur Relance.canal si possible
    canal = relance.canal.lower() if isinstance(relance.canal, str) else "sms"
    if canal not in {"sms", "whatsapp"}:
        canal = os.getenv("TWILIO_CHANNEL", "whatsapp").lower()
        canal = "whatsapp" if canal == "whatsapp" else "sms"
    send_message_async(to_number=tel, body=body, channel=canal)


def send_retard_notification(eleve: Eleve, solde_restant) -> None:
    tel = _safe_phone(getattr(eleve.responsable_principal, "telephone", None))
    if not tel:
        return
    body = build_retard_message(eleve, solde_restant)
    # Par défaut WhatsApp
    send_payment_confirmation_async(to_number=tel, body=body)
    # SMS bref
    sms_body = f"Retard de paiement: {eleve.nom_complet}, solde {_format_amount(solde_restant)}"
    send_message_async(to_number=tel, body=sms_body, channel="sms")
