from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.constants import RECORD_TYPES
from fabriclib.dns.validate_record import validate_record


def add_record(actor, key, rtype, form, source="cli"):
    """Validate and add a record to zone `key` in vars.yaml. Returns it."""
    if rtype not in RECORD_TYPES:
        raise ValidationError("unsupported record type")
    record = validate_record(rtype, form)
    with vars_lock():
        data = load_vars()
        zone = (data.get("dns") or {}).get(key)
        if zone is None:
            raise ValidationError("unknown zone")
        existing = zone.setdefault(rtype, [])
        if rtype == "CNAME" and any(r.get("name") == record["name"] for r in existing):
            raise ValidationError("a CNAME with that name already exists")
        existing.append(record)
        save_vars(data)
    write_audit(actor, "DNS_ADD", f"zone={key} {rtype} {record}", source)
    return record
