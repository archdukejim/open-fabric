from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys

FIELDS = ("records", "record_types", "domain", "algorithm", "out")


def update_tsig_key(actor, name, changes, source="cli"):
    """Change what an existing TSIG key may update (its secret is untouched).
    `changes` may set records (a list; [] means any name in the zone),
    record_types, domain, algorithm, out. Run apply afterwards. Returns the
    key as stored."""
    unknown = set(changes) - set(FIELDS)
    if unknown:
        raise ValidationError(f"cannot change {', '.join(sorted(unknown))}")
    with vars_lock():
        data = load_vars()
        keys = list(data.get("tsig_keys") or [])
        idx = next((i for i, k in enumerate(keys) if k.get("name") == name), None)
        if idx is None:
            raise ValidationError(f"no TSIG key named {name!r}")
        key = dict(keys[idx])
        for field, value in changes.items():
            if value in (None, [], ""):
                key.pop(field, None)
            else:
                key[field] = value
        keys[idx] = key
        data["tsig_keys"], _ = normalize_tsig_keys(keys, data.get("domain", ""))
        save_vars(data)
    stored = data["tsig_keys"][idx]
    write_audit(actor, "TSIG_UPDATE", f"key={name} {changes}", source)
    return stored
