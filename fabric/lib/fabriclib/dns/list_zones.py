from fabriclib.common.load_vars import load_vars
from fabriclib.dns.zone_name import zone_name


def list_zones():
    """[{key, name, records, reverse}] for every zone in vars.yaml (reverse:
    a hand-written in-addr.arpa / ip6.arpa zone)."""
    data = load_vars()
    zones = []
    for key, zone in (data.get("dns") or {}).items():
        count = sum(len(v) for v in (zone or {}).values() if isinstance(v, list))
        name = zone_name(data, key)
        zones.append({"key": key, "name": name, "records": count,
                      "reverse": name.endswith((".in-addr.arpa", ".ip6.arpa"))})
    return zones
