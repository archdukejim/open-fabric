from fabriclib.common.errors import ValidationError

DEFAULT_MAX_DAYS = 1825


def valid_days(v, days):
    """Validity in days for a manually issued certificate: 1 ..
    pki_manual_max_days (default 5 years)."""
    cap = int(v.get("pki_manual_max_days") or DEFAULT_MAX_DAYS)
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValidationError("validity must be a number of days")
    if not 1 <= days <= cap:
        raise ValidationError(f"validity must be 1 to {cap} days (pki_manual_max_days)")
    return days
