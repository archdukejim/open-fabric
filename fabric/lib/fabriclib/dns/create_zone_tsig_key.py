from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.add_tsig_key import add_tsig_key
from fabriclib.dns.list_zones import list_zones
from fabriclib.dns.rfc2136_settings import rfc2136_settings

# scope -> what the key may change in its zone
SCOPES = {
    "acme-hosts": "TXT at _acme-challenge.<host> for the listed hosts only (certbot DNS-01)",
    "acme-zone": "TXT at any _acme-challenge name in the zone (certbot DNS-01)",
    "any-name": "the chosen record types at any name in the zone",
}
ANY_NAME_TYPES = ("A", "AAAA", "CNAME", "TXT", "SRV", "MX")


def create_zone_tsig_key(actor, name, zone, scope, hosts=(), types=("TXT",), secret=None, source="web"):
    """The web UI's "new TSIG key for a zone": a key limited to one of
    fabric's forward zones and one of SCOPES (deny-by-default otherwise).
    `secret` keeps an existing client's key working; else one is generated.
    The rfc2136.ini path is always fabric's default (never caller-chosen).
    Run apply afterwards. Returns (entry, secret, rfc2136_ini_text)."""
    forward = {z["name"] for z in list_zones() if not z["reverse"]}
    if zone not in forward:
        raise ValidationError(f"{zone!r} is not one of this fabric's forward zones")
    entry = {"name": str(name).strip(), "domain": zone, "record_types": ["TXT"]}
    if scope == "acme-hosts":
        entry["records"] = [h.strip() for h in hosts if h.strip()]
        if not entry["records"]:
            raise ValidationError("list at least one host that may prove its name")
    elif scope == "acme-zone":
        entry["primary"] = True
    elif scope == "any-name":
        types = [t for t in types if t]
        if not types or any(t not in ANY_NAME_TYPES for t in types):
            raise ValidationError(f"record types must be among {', '.join(ANY_NAME_TYPES)}")
        entry.update(any_name=True, record_types=types)
    else:
        raise ValidationError("unknown scope")
    key, secret = add_tsig_key(actor, entry, (secret or "").strip() or None, source=source)
    return key, secret, rfc2136_settings(load_vars(), key, secret)
