import ipaddress
import re

from fabriclib.common.errors import ValidationError

# a name RPZ can carry: lowercase labels, underscores allowed (lists use them), a single label for a whole TLD
LABEL = r"[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?"
NAME_RE = re.compile(rf"^(?=.{{1,253}}$){LABEL}(\.{LABEL})*$")


def _names(v, key, own):
    """Purpose: one rules setting (dns_filter_allow or dns_filter_block), checked and normalised.
    Inputs:  v — rendered vars; key — the setting's name; own — fabric's own domains (never filtered, so never a rule).
    Returns: the names, lowercased, without a trailing dot or duplicates.
    Fails:   ValidationError for a setting that is not a list, or a name that is not one, or inside fabric's domains.
    Feeds:   check_filter_settings."""
    value = v.get(key) or []
    if not isinstance(value, list):
        raise ValidationError(f"{key} must be a list of names")
    out = []
    for raw in value:
        name = str(raw).strip().rstrip(".").lower()
        if not NAME_RE.match(name):
            raise ValidationError(f"{key}: {raw!r} is not a DNS name")
        if any(name == d or name.endswith("." + d) for d in own):
            raise ValidationError(f"{key}: {name} is inside fabric's own domains, which are never filtered")
        out.append(name)
    return list(dict.fromkeys(out))


def check_filter_settings(v):
    """Purpose: refuse BIND resolver settings that cannot work (manual 1.12.2.6–1.12.2.8), before anything is rendered;
             the rules are normalised in place (lowercase, no trailing dot, no duplicates).
    Inputs:  v — rendered vars (dns_filter_lists, dns_filter_allow, dns_filter_block, dns_filter_upstreams, domain,
             org_domain, ad_domain); changed in place.
    Returns: None.
    Fails:   ValidationError naming the setting: a list without an http(s) url, the same url twice; an allow or
             block that is not a name, is inside fabric's domains, or is both allowed and blocked; an upstream
             without an IP address or a certificate name.
    Feeds:   deploy/check_settings (when dns_filter is bind)."""
    lists = v.get("dns_filter_lists") or []
    if not isinstance(lists, list):
        raise ValidationError("dns_filter_lists must be a list of {name, url}")
    seen = set()
    for item in lists:
        url = str((item or {}).get("url") or "").strip() if isinstance(item, dict) else ""
        if not url.startswith(("https://", "http://")):
            raise ValidationError(f"dns_filter_lists: {item!r} needs an http(s) url")
        if url in seen:
            raise ValidationError(f"dns_filter_lists: {url} is listed twice")
        seen.add(url)
    own = [d for d in (v.get("domain"), v.get("org_domain"), v.get("ad_domain")) if d]
    v["dns_filter_allow"] = _names(v, "dns_filter_allow", own)
    v["dns_filter_block"] = _names(v, "dns_filter_block", own)
    both = set(v["dns_filter_allow"]) & set(v["dns_filter_block"])
    if both:
        raise ValidationError(f"allowed and blocked at once: {', '.join(sorted(both))}")
    ups = v.get("dns_filter_upstreams") or []
    if not isinstance(ups, list):
        raise ValidationError("dns_filter_upstreams must be a list of {address, name}")
    for u in ups:
        try:
            ipaddress.ip_address(str((u or {}).get("address")))
        except ValueError:
            raise ValidationError(f"dns_filter_upstreams: {u!r} needs an IP address") from None
        if not NAME_RE.match(str(u.get("name") or "").lower()) or "." not in str(u.get("name")):
            raise ValidationError(f"dns_filter_upstreams: {u!r} needs the name its certificate is checked against")
