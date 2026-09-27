from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.constants import RECORD_TYPES
from fabriclib.dns.format_value import format_value
from fabriclib.dns.sync_status import sync_status
from fabriclib.dns.zone_name import zone_name


def zone_detail(key):
    """One zone: its records (with display values) and BIND sync status."""
    data = load_vars()
    zone = (data.get("dns") or {}).get(key)
    if zone is None:
        raise ValidationError("unknown zone")
    records = []
    for rtype in RECORD_TYPES:
        for idx, rec in enumerate(zone.get(rtype) or []):
            records.append({"type": rtype, "index": idx, "name": rec.get("name") or "",
                            "value": format_value(rtype, rec)})
    name = zone_name(data, key)
    return {"key": key, "name": name, "records": records, "status": sync_status(name)[1]}
