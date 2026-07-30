import os
import threading
import logging
from typing import Optional, Literal

from .utils_security import mask_secret

try:
    from twilio.rest import Client
except Exception:
    Client = None  # Twilio not installed yet

Channel = Literal["sms", "whatsapp"]

logger = logging.getLogger(__name__)


def _get_client() -> Optional[Client]:
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    if not account_sid or not auth_token:
        logger.debug(
            "Twilio client not configured (SID=%s, Token=%s)",
            mask_secret(account_sid),
            mask_secret(auth_token),
        )
        return None
    if Client is None:
        logger.debug("Twilio SDK not installed; Client is None")
        return None
    try:
        return Client(account_sid, auth_token)
    except Exception as e:
        logger.warning(
            "Failed to instantiate Twilio Client (SID=%s): %s",
            mask_secret(account_sid),
            str(e),
        )
        return None


def _format_recipient(number: str, channel: Channel) -> str:
    number = (number or "").strip()
    if channel == "whatsapp":
        if not number.startswith("whatsapp:"):
            return f"whatsapp:{number}"
    return number


def send_message(
    to_number: str,
    body: str,
    channel: Channel = "sms",
    status_callback: Optional[str] = None,
) -> tuple[bool, Optional[str]]:
    """Send an SMS or WhatsApp message using Twilio.

    Returns (ok, sid_or_error).
    """
    if os.getenv("TWILIO_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        logger.info("Twilio disabled via env TWILIO_ENABLED")
        return False, "TWILIO_DISABLED"

    client = _get_client()
    if not client:
        logger.warning("Twilio client unavailable; check env and installation")
        return False, "TWILIO_CLIENT_UNAVAILABLE"

    # Prefer Messaging Service SID if provided; else resolve sender number per channel
    messaging_service_sid = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
    from_number = None
    if not messaging_service_sid:
        # Sender: prefer channel-specific env, then fallback to TWILIO_FROM
        if channel == "whatsapp":
            from_number = os.getenv("TWILIO_FROM_WHATSAPP")
        else:
            from_number = os.getenv("TWILIO_FROM_SMS")
        if not from_number:
            from_number = os.getenv("TWILIO_FROM")

        if not from_number:
            logger.warning("Twilio sender missing (TWILIO_FROM[_WHATSAPP/_SMS]) and no Messaging Service SID")
            return False, "TWILIO_FROM_MISSING"

    try:
        to_formatted = _format_recipient(to_number, channel)
        # Build arguments depending on Messaging Service vs direct sender
        create_kwargs = {
            "to": to_formatted,
            "body": body,
            "status_callback": status_callback or os.getenv("TWILIO_STATUS_CALLBACK"),
        }
        if messaging_service_sid:
            create_kwargs["messaging_service_sid"] = messaging_service_sid
            from_logged = f"MSG:{mask_secret(messaging_service_sid, show=6)}"
        else:
            from_formatted = _format_recipient(from_number, channel)
            create_kwargs["from_"] = from_formatted
            from_logged = mask_secret(from_formatted)

        msg = client.messages.create(**create_kwargs)
        logger.info(
            "Twilio message queued (to=%s, from=%s, sid=%s)",
            mask_secret(to_formatted),
            from_logged,
            mask_secret(getattr(msg, "sid", ""), show=6),
        )
        return True, getattr(msg, "sid", None) or "SENT"
    except Exception as e:
        logger.error(
            "Twilio send failed (to=%s, from=%s): %s",
            mask_secret(to_number),
            mask_secret(from_number),
            str(e),
        )
        return False, str(e)


def send_message_async(
    to_number: str,
    body: str,
    channel: Channel = "sms",
    status_callback: Optional[str] = None,
) -> None:
    """Fire-and-forget async send to avoid blocking the request cycle."""

    def _worker():
        try:
            send_message(to_number, body, channel=channel, status_callback=status_callback)
        except Exception:
            pass

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def send_payment_confirmation_async(
    to_number: Optional[str],
    body: str,
    channel_env: Optional[str] = None,
    status_callback: Optional[str] = None,
) -> None:
    """Helper tailored for payments: chooses channel from env if not provided and no-ops if no number."""
    if not to_number:
        return
    channel_value = (channel_env or os.getenv("TWILIO_CHANNEL", "whatsapp")).strip().lower()
    channel: Channel = "whatsapp" if channel_value == "whatsapp" else "sms"
    send_message_async(to_number=to_number, body=body, channel=channel, status_callback=status_callback)
