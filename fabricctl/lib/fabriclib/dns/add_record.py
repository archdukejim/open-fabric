from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.constants import RECORD_TYPES
from fabriclib.dns.validate_record import validate_record


def add_record(actor, key, rtype, form, source="cli"):
    """Purpose: Validate a DNS record and append it to one zone in vars.yaml (`dns:`). Run apply afterwards to publish
             it.
    Inputs:  actor — str, who asks (audit).
             key — str, the zone key in `dns:` (dynamic_zone_var is the main domain).
             rtype — one of RECORD_TYPES (A, AAAA, CNAME, MX, TXT, SRV).
             form — dict of user fields as validate_record expects (name, ip, target, text, priority, weight, port).
             source — "cli" (default) or "web". Reads and writes vars.yaml under vars_lock.
    Returns: the stored record dict, shaped per validate_record (e.g. {"name", "ip"} for A).
    Fails:   ValidationError "unsupported record type", "unknown zone", "a CNAME with that name already exists", or one
             from validate_record; OSError or yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   agent route POST /v1/zones/<key>/records (fabricctl/lib/agent/server.py, called by webui/server.py); the
             interactive zone editor (fabricctl/lib/interactive.py).
    Notes:   only CNAME-vs-CNAME clashes are refused here; a CNAME beside other records of the same name is not checked.
    """
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
