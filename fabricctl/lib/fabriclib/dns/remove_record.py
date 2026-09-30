from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def remove_record(actor, key, rtype, index, expected_name, source="cli"):
    """Remove record `index` of `rtype` from zone `key`, only if its name is
    still `expected_name` (so a stale view cannot delete the wrong record)."""
    with vars_lock():
        data = load_vars()
        records = ((data.get("dns") or {}).get(key) or {}).get(rtype) or []
        if not 0 <= index < len(records) or (records[index].get("name") or "") != expected_name:
            raise ValidationError("record changed since it was shown; reload and try again")
        removed = records.pop(index)
        if not records:
            del data["dns"][key][rtype]
        save_vars(data)
    write_audit(actor, "DNS_DELETE", f"zone={key} {rtype} {removed}", source)
    return removed
