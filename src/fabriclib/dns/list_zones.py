from fabriclib.common.load_vars import load_vars
from fabriclib.dns.zone_name import zone_name


def list_zones():
    """Purpose: Every zone in vars.yaml (`dns:`) with its record count, for the zone list.
    Inputs:  none. Reads vars.yaml.
    Returns: [{"key", "name", "records" (count over all list-valued fields), "reverse" (True for a hand-written
             in-addr.arpa / ip6.arpa zone)}] in vars order.
    Fails:   OSError or yaml.YAMLError from load_vars.
    Feeds:   agent route GET /v1/zones (fabric-agent, src/agent/, called by the web UI); create_zone_tsig_key.
    """
    data = load_vars()
    zones = []
    for key, zone in (data.get("dns") or {}).items():
        count = sum(len(v) for v in (zone or {}).values() if isinstance(v, list))
        name = zone_name(data, key)
        zones.append({"key": key, "name": name, "records": count,
                      "reverse": name.endswith((".in-addr.arpa", ".ip6.arpa"))})
    return zones
