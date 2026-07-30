import os
from typing import Optional


def _mask(value: Optional[str], show: int = 4) -> str:
    if not value:
        return "<empty>"
    s = str(value)
    if len(s) <= show:
        return "*" * len(s)
    return f"{'*' * (len(s) - show)}{s[-show:]}"


def _enabled() -> bool:
    return os.getenv("TWILIO_ENABLED", "false").strip().lower() in {"1", "true", "yes"}


def check_twilio_env() -> None:
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    from_wa = os.getenv("TWILIO_FROM_WHATSAPP")
    from_sms = os.getenv("TWILIO_FROM_SMS")
    from_any = os.getenv("TWILIO_FROM")

    print("--- Twilio environment check ---")
    print("TWILIO_ENABLED:", os.getenv("TWILIO_ENABLED"))
    print("TWILIO_ACCOUNT_SID:", _mask(sid, 6))
    print("TWILIO_AUTH_TOKEN:", _mask(token, 6))
    print("TWILIO_FROM_WHATSAPP:", from_wa or "<unset>")
    print("TWILIO_FROM_SMS:", from_sms or "<unset>")
    print("TWILIO_FROM (fallback):", from_any or "<unset>")

    problems = []
    if not _enabled():
        problems.append("TWILIO_ENABLED is not 'true' (set to 'true' to enable sending)")
    if not sid:
        problems.append("TWILIO_ACCOUNT_SID is missing (must start with 'AC')")
    if not token:
        problems.append("TWILIO_AUTH_TOKEN is missing")
    if not (from_wa or from_sms or from_any):
        problems.append("No sender set (TWILIO_FROM_WHATSAPP or TWILIO_FROM_SMS or TWILIO_FROM)")

    if problems:
        print("\n⚠️ Issues detected:")
        for p in problems:
            print(" -", p)
        print("\nHow to set in PowerShell (current session):")
        print("  $env:TWILIO_ENABLED = 'true'")
        print("  $env:TWILIO_ACCOUNT_SID = 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx'")
        print("  $env:TWILIO_AUTH_TOKEN  = 'yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy'")
        print("  $env:TWILIO_FROM_WHATSAPP = 'whatsapp:+14155238886'  # or TWILIO_FROM_SMS = '+1XXXXXXXXXX'")
    else:
        print("\n✅ Twilio variables look OK.")


if __name__ == "__main__":
    check_twilio_env()
