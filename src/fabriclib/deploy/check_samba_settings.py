import re

from fabriclib.common.errors import ValidationError

# the password policy's keys (D89): every one is the admin's, none has a default
POLICY_KEYS = {"minimum_length": (0, 64), "history": (0, 24), "minimum_age_days": (0, 998),
               "maximum_age_days": (0, 999), "lockout_threshold": (0, 999), "lockout_minutes": (0, 99999),
               "lockout_window_minutes": (0, 99999)}
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_NETBIOS = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,14}$")


def check_samba_settings(v):
    """Purpose: refuse a Windows-domain configuration fabric cannot provision correctly (manual 2.11.2, 2.1.9.7),
             before anything is rendered: the domain (D87), the NetBIOS names, the password policy (D89).
    Inputs:  v — rendered settings: install_samba, ad_domain, domain, hostname, ad_netbios, ad_password_policy,
             ad_old_password_minutes, ad_rpc_ports.
    Returns: None (nothing is checked while install_samba is off).
    Fails:   ValidationError naming the first problem: no or an invalid ad_domain; ad_domain equal to fabric's domain
             (same-domain mode, refused until build step S1.6) or a parent of it; a NetBIOS domain name or host name
             Windows cannot use (more than 15 characters); a missing, unknown or out-of-range password-policy key;
             a policy whose minimum age is not below its maximum, or whose lockout is shorter than its window; an
             invalid old-password window or RPC range.
    Feeds:   deploy/check_settings."""
    if not v.get("install_samba"):
        return
    ad, domain = str(v.get("ad_domain") or ""), str(v.get("domain") or "").lower()
    labels = ad.split(".")
    if not ad:
        raise ValidationError("install_samba needs ad_domain: the AD domain, chosen once (manual 2.1.9.7; "
                              f"recommended: ad.{domain})")
    if len(labels) < 2 or not all(_LABEL.match(x) for x in labels) or len(ad) > 253:
        raise ValidationError(f"ad_domain {ad!r} is not a valid DNS domain of two labels or more")
    if ad == domain:
        raise ValidationError(f"ad_domain equal to domain ({ad}: same-domain mode) is not supported yet "
                              "(build step S1.6); use a sub-domain such as ad." + domain)
    if domain.endswith("." + ad):
        raise ValidationError(f"ad_domain {ad} is a parent of fabric's domain {domain}: AD's zone would hold "
                              "fabric's; use a sub-domain such as ad." + domain)
    if not _NETBIOS.match(str(v.get("ad_netbios") or "")):
        raise ValidationError(f"ad_netbios {v.get('ad_netbios')!r}: at most 15 letters, digits or hyphens")
    if not _NETBIOS.match(str(v.get("hostname") or "").upper()):
        raise ValidationError(f"the host name {v.get('hostname')!r} is the domain controller's NetBIOS name: at "
                              "most 15 letters, digits or hyphens")
    policy = v.get("ad_password_policy") or {}
    missing = sorted((set(POLICY_KEYS) | {"complexity"}) - set(policy))
    if missing:
        raise ValidationError("the password policy is the admin's (D89), with no defaults: ad_password_policy "
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
        raise ValidationError("ad_password_policy.minimum_age_days must be below maximum_age_days")
    if policy["lockout_minutes"] and policy["lockout_minutes"] < policy["lockout_window_minutes"]:
        raise ValidationError("ad_password_policy.lockout_minutes (0: until an admin unlocks) must be at least "
                              "lockout_window_minutes, as AD requires")
    if not 0 <= int(v.get("ad_old_password_minutes", 0)) <= 99999:
        raise ValidationError("ad_old_password_minutes must be from 0 to 99999")
    m = re.fullmatch(r"(\d+)-(\d+)", str(v.get("ad_rpc_ports") or ""))
    if not m or not 1024 < int(m.group(1)) <= int(m.group(2)) <= 65535:
        raise ValidationError(f"ad_rpc_ports {v.get('ad_rpc_ports')!r} must be a range low-high above 1024")
