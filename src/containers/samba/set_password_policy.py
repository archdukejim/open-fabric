import ldb

NEVER = -0x8000000000000000          # AD's "never" for an age or a lockout duration
TICKS_PER_MINUTE = 60 * 10 ** 7      # AD counts durations in 100-nanosecond ticks, negative
COMPLEX = 1                          # pwdProperties: DOMAIN_PASSWORD_COMPLEX


def _ticks(minutes):
    """Purpose: a duration as AD stores it.
    Inputs:  minutes — int; 0 means never.
    Returns: str, negative ticks, or AD's "never".
    Fails:   never.
    Feeds:   set_password_policy."""
    return str(NEVER if minutes == 0 else -minutes * TICKS_PER_MINUTE)


def set_password_policy(samdb, policy):
    """Purpose: the domain's password policy as the admin set it (2.1.6.13, manual 1.6.3.8), written on the domain
             object; only what differs is written.
    Inputs:  samdb — SamDB; policy — dict with every key of fabric's ad_password_policy (minimum_length, complexity,
             history, minimum_age_days, maximum_age_days (0: never expires), lockout_threshold (0: never locked),
             lockout_minutes (0: until an admin unlocks), lockout_window_minutes).
    Returns: list of str, the attributes changed.
    Fails:   KeyError for a missing key (fabric checks the policy first: check_samba_settings); ldb.LdbError if AD
             refuses a value.
    Feeds:   converge."""
    base = str(samdb.domain_dn())
    current = samdb.search(base=base, scope=ldb.SCOPE_BASE,
                           attrs=["minPwdLength", "pwdProperties", "pwdHistoryLength", "minPwdAge", "maxPwdAge",
                                  "lockoutThreshold", "lockoutDuration", "lockOutObservationWindow"])[0]
    props = int(str(current.get("pwdProperties", ["0"])[0]))
    props = props | COMPLEX if policy["complexity"] else props & ~COMPLEX
    wanted = {"minPwdLength": str(policy["minimum_length"]), "pwdProperties": str(props),
              "pwdHistoryLength": str(policy["history"]),
              "minPwdAge": str(-policy["minimum_age_days"] * 24 * 60 * TICKS_PER_MINUTE),
              "maxPwdAge": _ticks(policy["maximum_age_days"] * 24 * 60),
              "lockoutThreshold": str(policy["lockout_threshold"]),
              "lockoutDuration": _ticks(policy["lockout_minutes"]),
              "lockOutObservationWindow": str(-policy["lockout_window_minutes"] * TICKS_PER_MINUTE)}
    changed = {k: v for k, v in wanted.items() if str(current.get(k, [""])[0]) != v}
    if changed:
        samdb.modify(ldb.Message.from_dict(samdb, {"dn": base, **changed}, ldb.FLAG_MOD_REPLACE))
    return sorted(changed)
