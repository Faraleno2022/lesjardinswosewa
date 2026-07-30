from typing import Optional


def mask_secret(value: Optional[str], show: int = 4) -> str:
    """Return a masked representation of a secret.

    Examples:
      mask_secret("AC1234567890", show=4) => "**********7890"
      mask_secret(None) => "<none>"
    """
    if value is None:
        return "<none>"
    s = str(value)
    if not s:
        return ""
    if len(s) <= show:
        return "*" * len(s)
    return ("*" * (len(s) - show)) + s[-show:]
