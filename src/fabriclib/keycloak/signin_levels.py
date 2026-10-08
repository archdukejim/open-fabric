from fabriclib.common.errors import ValidationError

# second-factor levels, weakest first (manual 5.8.2.6.1): "any" accepts whichever the person enrolled, so it is weaker
# than requiring one; a passkey (unlocked on the device, bound to the site's name) is the strongest
LEVELS = ("none", "any", "totp", "passkey")


def signin_level(value):
    """Purpose: a second-factor setting checked and normalised.
    Inputs:  value — the setting (None or "" = none).
    Returns: str, one of LEVELS.
    Fails:   ValidationError for anything else.
    Feeds:   admin_level, ensure_signin_flows, check_settings, the security command and page."""
    level = str(value or "none").strip().lower()
    if level not in LEVELS:
        raise ValidationError(f"a second factor must be one of {', '.join(LEVELS)} (got {value!r})")
    return level


def admin_level(v):
    """Purpose: the admin tools' effective second factor: their own setting, or everyone's when that is stronger
             (the admin tools never ask for less than every sign-in does).
    Inputs:  v — vars: signin_admin_second_factor, signin_everyone_second_factor.
    Returns: str, one of LEVELS.
    Fails:   ValidationError from signin_level.
    Feeds:   ensure_signin_flows, the security command and page."""
    own, everyone = (signin_level(v.get(k)) for k in ("signin_admin_second_factor", "signin_everyone_second_factor"))
    return max(own, everyone, key=LEVELS.index)
