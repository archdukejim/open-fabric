from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.add_filter_rule import KEYS


def remove_filter_rule(actor, kind, name, source="cli"):
    """Purpose: take a name out of the DNS filter's allows or blocks (manual 1.12.2.14). Saved in vars.yaml; applied by
             the next apply.
    Inputs:  actor — who asks (audit); kind — "allow" or "block"; name — as listed; source — "cli" or "web".
    Returns: {"kind", "name"}.
    Fails:   ValidationError for another kind or a name not in that rule; OSError or yaml errors from the vars file and
             the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/rules/delete)."""
    if kind not in KEYS:
        raise ValidationError("kind: allow or block")
    name = str(name or "").strip().rstrip(".").lower()
    with vars_lock():
        data = load_vars()
        names = list(data.get(KEYS[kind]) or [])
        if name not in names:
            raise ValidationError(f"{name} is not {'allowed' if kind == 'allow' else 'blocked'} by a rule")
        data[KEYS[kind]] = [n for n in names if n != name]
        save_vars(data)
    write_audit(actor, f"DNS_FILTER_UN{kind.upper()}", name, source)
    return {"kind": kind, "name": name}
