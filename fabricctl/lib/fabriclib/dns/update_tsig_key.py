from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys

FIELDS = ("records", "any_name", "record_types", "domain", "algorithm", "out")


def update_tsig_key(actor, name, changes, source="cli"):
    """Purpose: Change what an existing TSIG key may update; its secret is untouched. Run apply afterwards.
    Inputs:  actor — str, who asks (audit).
             name — str key name.
             changes — dict with keys from FIELDS: records (list), any_name (True), record_types, domain, algorithm,
             out; a value of None, [] or "" removes that field.
             source — "cli" (default) or "web". Reads/writes vars.yaml under vars_lock.
    Returns: the key dict as stored after normalize_tsig_keys.
    Fails:   ValidationError "cannot change …" (unknown field), "no TSIG key named …", or one from normalize_tsig_keys;
             OSError or yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   run_tsig_command (`fabricctl tsig update`).
    """
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
