from fabriclib.common.errors import ValidationError

MIN_LEFT_DAYS = 7          # a renewal leaves at least this long (2.1.5.4): nights to retry before anything expires
MIN_ROOT_DAYS = 365


def _days(v, key):
    """Purpose: one lifetime setting as whole days.
    Inputs:  v — settings; key — the setting's name.
    Returns: int.
    Fails:   ValidationError when it is not a whole number.
    Feeds:   check_cert_lifetimes."""
    value = v.get(key)
    if isinstance(value, bool) or not str(value).strip().isdigit():
        raise ValidationError(f"{key} must be a whole number of days (got {value!r})")
    return int(value)


def check_cert_lifetimes(v):
    """Purpose: refuse certificate lifetimes that could not work (manual 2.1.5.4, 2.1.5.6).
    Inputs:  v — the rendered settings: cert_service_days, cert_renew_after_days, cert_root_ca_days.
    Returns: None.
    Fails:   ValidationError naming the setting: not a whole number of days; cert_renew_after_days under 1, or
             leaving under 7 days of the certificate (cert_service_days less it); cert_root_ca_days under 365.
    Feeds:   deploy/render_vars."""
    service, renew, root = (_days(v, k) for k in ("cert_service_days", "cert_renew_after_days", "cert_root_ca_days"))
    if renew < 1:
        raise ValidationError(f"cert_renew_after_days is {renew}: renewal starts at least a day after issue")
    if service - renew < MIN_LEFT_DAYS:
        raise ValidationError(f"cert_renew_after_days {renew} leaves {service - renew} day(s) of a "
                              f"{service}-day certificate: leave at least {MIN_LEFT_DAYS}, so failed nights can be "
                              f"retried before it expires (cert_service_days at least {renew + MIN_LEFT_DAYS})")
    if root < MIN_ROOT_DAYS:
        raise ValidationError(f"cert_root_ca_days is {root}: the root CA lives at least {MIN_ROOT_DAYS} days "
                              "(its intermediate lives a year less)")
