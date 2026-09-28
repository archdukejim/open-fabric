from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.constants import RECORD_TYPES
from fabriclib.dns.format_value import format_value
from fabriclib.dns.ptr_for_ip import ptr_for_ip
from fabriclib.dns.sync_status import sync_status
from fabriclib.dns.zone_name import zone_name


def zone_detail(key):
    """One zone: its records (with display values; A/AAAA also say where
    their automatic PTR goes, or why there is none) and BIND sync status."""
    data = load_vars()
    zone = (data.get("dns") or {}).get(key)
    if zone is None:
        raise ValidationError("unknown zone")
    records = []
    for rtype in RECORD_TYPES:
        for idx, rec in enumerate(zone.get(rtype) or []):
            entry = {"type": rtype, "index": idx, "name": rec.get("name") or "",
                     "value": format_value(rtype, rec)}
            if rtype in ("A", "AAAA"):
                rzone, label = ptr_for_ip(rec.get("ip"))
                entry["ptr"] = f"{label}.{rzone}" if rzone else ""
                entry["ptr_note"] = "" if rzone else label
            records.append(entry)
    name = zone_name(data, key)
    return {"key": key, "name": name, "records": records, "status": sync_status(name)[1]}
