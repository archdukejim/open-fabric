from fabriclib.common.load_vars import load_vars
from fabriclib.dns.zone_name import zone_name


def list_zones():
    """[{key, name, records}] for every zone in vars.yaml."""
    data = load_vars()
    zones = []
    for key, zone in (data.get("dns") or {}).items():
        count = sum(len(v) for v in (zone or {}).values() if isinstance(v, list))
        zones.append({"key": key, "name": zone_name(data, key), "records": count})
    return zones
