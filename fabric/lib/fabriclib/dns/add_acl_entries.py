import ipaddress
import re

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit

NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")
RESERVED = {"any", "none", "localhost", "localnets", "tsig-updaters"}
BUILTIN_MATCHES = {"any", "none", "localhost", "localnets"}


def _check_entry(entry, data, acl):
    """One BIND address-match-list element, normalized: an IP or CIDR,
    `key <tsig key>`, a built-in (any/none/localhost/localnets), another
    ACL, each optionally negated with a leading `!`."""
    entry = " ".join(str(entry).split())
    neg, body = ("!", entry[1:].strip()) if entry.startswith("!") else ("", entry)
    if body.startswith("key "):
        name = body[4:].strip()
        if not any(k.get("name") == name for k in data.get("tsig_keys") or []):
            raise ValidationError(f"no TSIG key named {name!r} (fabricctl tsig list)")
        return f'{neg}key "{name}"'
    if body in BUILTIN_MATCHES or body == "tsig-updaters":
        return neg + body
    if body in (data.get("bind_acls") or {}):
        if body == acl:
            raise ValidationError("an ACL cannot contain itself")
        return f'{neg}"{body}"'
    try:
        net = ipaddress.ip_network(body, strict=False)
    except ValueError:
        raise ValidationError(f"not an IP, CIDR, 'key <name>', ACL or any/none/localhost/localnets: {entry!r}") from None
    return neg + (str(net.network_address) if net.num_addresses == 1 and "/" not in body else str(net))


def add_acl_entries(actor, acl, entries, source="cli"):
    """Create BIND ACL `acl` or add entries to it (bind_acls in vars.yaml).
    Every ACL may query fabric's zones (allow-query). Run apply afterwards.
    Returns the ACL's entries."""
    if not NAME_RE.match(acl) or acl in RESERVED:
        raise ValidationError(f"invalid ACL name {acl!r}")
    if not entries:
        raise ValidationError("give at least one entry")
    with vars_lock():
        data = load_vars()
        acls = dict(data.get("bind_acls") or {})
        current = list(acls.get(acl) or [])
        for entry in entries:
            norm = _check_entry(entry, data, acl)
            if norm not in current:
                current.append(norm)
        acls[acl] = current
        data["bind_acls"] = acls
        save_vars(data)
    write_audit(actor, "ACL_ADD", f"acl={acl} entries={list(entries)}", source)
    return current
