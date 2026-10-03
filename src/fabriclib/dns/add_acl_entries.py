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
    """Purpose: Validate one BIND address-match-list entry and return it in the form named.conf needs.
    Inputs:  entry — str: an IP or CIDR, `key <tsig key>`, any/none/localhost/localnets/tsig-updaters, or the name of
             another ACL in bind_acls; a leading `!` negates it; whitespace is collapsed.
             data — the loaded vars.yaml dict (reads tsig_keys and bind_acls).
             acl — str, the ACL being edited (it may not contain itself).
    Returns: the normalized entry (str): `key "<name>"`, a quoted ACL name, a built-in, a bare IP (one address given
             without a prefix) or a CIDR network, with any `!` kept.
    Fails:   ValidationError "no TSIG key named …", "an ACL cannot contain itself", or "not an IP, CIDR, 'key <name>',
             ACL or any/none/localhost/localnets: …".
    Feeds:   add_acl_entries.
    Notes:   a key name typed with quotes (`key "npm"`) is looked up with its quotes and so is not found.
    """
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
    """Purpose: Create BIND ACL `acl` in vars.yaml (bind_acls) or add entries to it. Every ACL may query fabric's zones
             (allow-query). Run apply afterwards to render it.
    Inputs:  actor — str, who asks (audit).
             acl — str matching NAME_RE (letter or digit, then up to 62 letters, digits, _ or -), not reserved (any,
             none, localhost, localnets, tsig-updaters).
             entries — non-empty list of str (see _check_entry); entries already present are skipped.
             source — "cli" (default) or "web", for the audit line. Reads and writes vars.yaml under vars_lock.
    Returns: the ACL's full entry list after the change (list of str).
    Fails:   ValidationError "invalid ACL name …", "give at least one entry", or one from _check_entry; OSError or
             yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   run_acl_command (`fabricctl acl add`); NAME_RE and RESERVED are reused by set_acl_policy and set_key_acls.
    """
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
