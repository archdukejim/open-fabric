from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns_filter.check_filter_settings import check_filter_settings

KEYS = {"allow": "dns_filter_allow", "block": "dns_filter_block"}


def add_filter_rule(actor, kind, name, source="cli"):
    """Purpose: allow a name past every list, or block it whatever the lists say — the name and every name below it
             (manual 1.12.2.7, 1.12.2.14). A name in the other rule moves: allowing a blocked name unblocks it.
             Saved in vars.yaml; applied by the next apply.
    Inputs:  actor — who asks (audit); kind — "allow" or "block"; name — a DNS name; source — "cli" or "web".
    Returns: {"kind", "name" (normalised), "moved" (True when it left the other rule)}.
    Fails:   ValidationError for another kind, or from check_filter_settings (not a name, inside fabric's own
             domains); OSError or yaml errors from the vars file and the audit log.
    Feeds:   agent/post_dns_filter (POST /v1/dns-filter/rules)."""
    if kind not in KEYS:
        raise ValidationError("kind: allow or block")
    other = KEYS["block" if kind == "allow" else "allow"]
    name = str(name or "").strip().rstrip(".").lower()
    with vars_lock():
        data = load_vars()
        moved = name in (data.get(other) or [])
        trial = {**data, KEYS[kind]: [*(data.get(KEYS[kind]) or []), name],
                 other: [n for n in data.get(other) or [] if n != name]}
        check_filter_settings(trial)                           # normalises the rules in trial
        data[KEYS[kind]], data[other] = trial[KEYS[kind]], trial[other]
        save_vars(data)
    write_audit(actor, f"DNS_FILTER_{kind.upper()}", name + (" (moved)" if moved else ""), source)
    return {"kind": kind, "name": name, "moved": moved}
