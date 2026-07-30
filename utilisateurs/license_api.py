import base64
import hashlib
import hmac
import json
from datetime import datetime, time, timezone as dt_timezone

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import LicenceServeur


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except Exception:
        return {}


def _b64url(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt_secret():
    import license_manager
    return license_manager._DEV_SECRET


def _sign_token(licence):
    now = timezone.now()
    expires_dt = datetime.combine(licence.expires_at, time.max, tzinfo=dt_timezone.utc)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": "www.myschoolgn.space",
        "sub": licence.license_key,
        "iat": int(now.timestamp()),
        "exp": int(expires_dt.timestamp()),
        "school": licence.school,
        "edition": licence.edition,
        "deploiement": licence.deploiement,
        "machine_id": licence.machine_id.upper(),
        "status": licence.status,
        "expires_at": licence.expires_at.isoformat(),
    }
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
    signature = hmac.new(_jwt_secret(), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(signature)}"


def _license_response(licence):
    return {
        "status": licence.status,
        "signed_token": _sign_token(licence),
        "school": licence.school,
        "edition": licence.edition,
        "deploiement": licence.deploiement,
        "expires_at": licence.expires_at.isoformat(),
        "days_left": licence.days_left,
    }


def _find_licence(key):
    return LicenceServeur.objects.filter(license_key=key.strip().upper()).first()


@csrf_exempt
@require_POST
def activate_license(request):
    data = _json_body(request)
    key = (data.get("license_key") or "").strip().upper()
    machine_id = (data.get("machine_id") or "").strip().upper()
    hostname = (data.get("hostname") or "").strip()

    if not key or not machine_id:
        return JsonResponse({"status": "invalid", "reason": "Clé ou ID machine manquant."}, status=400)

    licence = _find_licence(key)
    if not licence:
        return JsonResponse({"status": "invalid", "reason": "Clé de licence inconnue."}, status=404)

    if not licence.is_usable_for(machine_id):
        if licence.machine_id.upper() != machine_id:
            reason = "Cette licence appartient à une autre machine."
        elif licence.status != "active":
            reason = "Cette licence n'est pas active."
        else:
            reason = "Cette licence est expirée."
        return JsonResponse({"status": "invalid", "reason": reason}, status=403)

    licence.hostname = hostname[:120]
    licence.activated_at = licence.activated_at or timezone.now()
    licence.last_check_at = timezone.now()
    licence.save(update_fields=["hostname", "activated_at", "last_check_at", "updated_at"])
    return JsonResponse(_license_response(licence))


@csrf_exempt
@require_POST
def verify_license(request):
    data = _json_body(request)
    key = (data.get("license_key") or "").strip().upper()
    machine_id = (data.get("machine_id") or "").strip().upper()

    if not key or not machine_id:
        return JsonResponse({"status": "invalid", "reason": "Clé ou ID machine manquant."}, status=400)

    licence = _find_licence(key)
    if not licence:
        return JsonResponse({"status": "invalid", "reason": "Clé de licence inconnue."}, status=404)

    if not licence.is_usable_for(machine_id):
        return JsonResponse({"status": "invalid", "reason": "Licence invalide, expirée ou suspendue."}, status=403)

    licence.last_check_at = timezone.now()
    licence.save(update_fields=["last_check_at", "updated_at"])
    return JsonResponse(_license_response(licence))
