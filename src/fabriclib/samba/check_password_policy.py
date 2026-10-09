from fabriclib.common.errors import ValidationError

# the password policy's keys (2.1.6.13); a new domain starts from DEFAULT_POLICY (2.1.6.35)
POLICY_KEYS = {"minimum_length": (0, 64), "history": (0, 24), "minimum_age_days": (0, 998),
               "maximum_age_days": (0, 999), "lockout_threshold": (0, 999), "lockout_minutes": (0, 99999),
               "lockout_window_minutes": (0, 99999)}
# a new domain's policy (2.1.6.35: the lighter of three, the owner's choice); changed any time
DEFAULT_POLICY = {"minimum_length": 12, "complexity": True, "history": 5, "minimum_age_days": 0, "maximum_age_days": 0,
                  "lockout_threshold": 10, "lockout_window_minutes": 15, "lockout_minutes": 15}


def check_password_policy(policy):
    """Purpose: the domain's password policy (2.1.6.13) checked as AD will take it: every key there, in range, and the
             rules between them — the minimum age below the maximum, and a lockout at least as long as the window
             after which failed sign-ins are forgotten (unless 0: locked until an admin unlocks).
    Inputs:  policy — dict: POLICY_KEYS and complexity.
    Returns: None.
    Fails:   ValidationError naming the first problem, with the values given.
    Feeds:   deploy/check_samba_settings (before anything is rendered); setup/ask_ad_domain (as the questions are
             answered, so they are asked again at once)."""
    missing = sorted((set(POLICY_KEYS) | {"complexity"}) - set(policy))
    if missing:
        raise ValidationError("the password policy is the admin's (2.1.6.13), with no defaults: ad_password_policy "
                              f"needs {', '.join(missing)}")
    unknown = sorted(set(policy) - set(POLICY_KEYS) - {"complexity"})
    if unknown:
        raise ValidationError(f"ad_password_policy has unknown keys: {', '.join(unknown)}")
    if not isinstance(policy["complexity"], bool):
        raise ValidationError("ad_password_policy.complexity must be true or false")
    for key, (low, high) in POLICY_KEYS.items():
        value = policy[key]
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise ValidationError(f"ad_password_policy.{key} must be a whole number from {low} to {high}")
    if policy["maximum_age_days"] and policy["minimum_age_days"] >= policy["maximum_age_days"]:
        raise ValidationError(f"a password may be changed again after {policy['minimum_age_days']} days but is valid "
                              f"for only {policy['maximum_age_days']}: the first must be below the second")
    if policy["lockout_minutes"] and policy["lockout_minutes"] < policy["lockout_window_minutes"]:
        raise ValidationError(f"an account stays locked {policy['lockout_minutes']} minutes, but failed sign-ins are "
                              f"forgotten only after {policy['lockout_window_minutes']}: AD needs the lock at least as "
                              "long as that window (or 0: locked until an admin unlocks it)")
