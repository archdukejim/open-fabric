import re

from fabriclib.common.errors import ValidationError

# a name RPZ can carry: lowercase labels, underscores allowed (lists use them), a single label for a whole TLD
LABEL = r"[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?"
NAME_RE = re.compile(rf"^(?=.{{1,253}}$){LABEL}(\.{LABEL})*$")


def rule_names(value, key, own):
    """Purpose: one rules setting (allow or block names: everyone's or a group's), checked and normalised.
    Inputs:  value — the setting's value (None for none); key — its name, for the messages; own — fabric's own
             domains (never filtered, so never a rule).
    Returns: the names, lowercased, without a trailing dot or duplicates.
    Fails:   ValidationError for a setting that is not a list, or a name that is not one, or inside fabric's domains.
    Feeds:   dns_filter/check_filter_settings, dns_filter/check_filter_groups."""
    value = value or []
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
