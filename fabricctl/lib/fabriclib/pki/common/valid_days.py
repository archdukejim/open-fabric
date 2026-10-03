from fabriclib.common.errors import ValidationError

DEFAULT_MAX_DAYS = 1825


def valid_days(v, days):
    """Purpose: Check the validity requested for a hand-issued certificate against the configured cap.
    Inputs:  v — fabric vars: pki_manual_max_days (default DEFAULT_MAX_DAYS = 1825, 5 years);
             days — int or numeric str.
    Returns: days as int, 1 .. cap.
    Fails:   ValidationError "validity must be a number of days" (not an integer); "validity must be 1 to
             <cap> days (pki_manual_max_days)"; ValueError if pki_manual_max_days itself is not a number.
    Feeds:   issue_key_pair, sign_csr (DEFAULT_MAX_DAYS also feeds ca_summary).
    """
    cap = int(v.get("pki_manual_max_days") or DEFAULT_MAX_DAYS)
    try:
        days = int(days)
    except (TypeError, ValueError):
        raise ValidationError("validity must be a number of days")
    if not 1 <= days <= cap:
        raise ValidationError(f"validity must be 1 to {cap} days (pki_manual_max_days)")
    return days
