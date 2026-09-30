import re

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.add_acl_entries import NAME_RE, RESERVED


def _is_key_entry(entry, key):
    """Purpose: Whether an ACL entry names a given TSIG key.
    Inputs:  entry — ACL entry (str); key — str key name.
    Returns: True for `key <name>` or `key "<name>"`, negated with `!` or not; else False.
    Fails:   never.
    Feeds:   set_key_acls.
    """
    return re.fullmatch(rf'!?key\s+"?{re.escape(key)}"?', str(entry).strip()) is not None


def set_key_acls(actor, key, add=(), drop=(), drop_all=False, source="cli"):
    """Purpose: Put a TSIG key in BIND ACLs (as `key "<name>"` entries; a missing ACL is created) and/or take it out of
             ACLs. Run apply afterwards.
    Inputs:  actor — str, who asks (audit).
             key — str key name; must exist in tsig_keys unless drop_all.
             add — iterable of ACL names (NAME_RE, not reserved).
             drop — iterable of existing ACL names.
             drop_all — bool: take it out of every ACL, which removing a key needs (BIND refuses a config whose ACL
             names an undefined key).
             source — "cli" (default) or "web". Reads/writes vars.yaml under vars_lock; also updates the key's own
             `acls` list, which apply re-applies on every render.
    Returns: sorted names of the ACLs that hold the key afterwards (list of str).
    Fails:   ValidationError "no TSIG key named …", "invalid ACL name …", "no ACL named …"; OSError or yaml.YAMLError
             from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   remove_tsig_key (drop_all), run_tsig_command (add --acl, update --acl / --drop-acl).
    Notes:   a `!key` exclusion counts as holding the key: adding the key to such an ACL leaves it excluded. The audit
             line is written only when something was asked for.
    """
    with vars_lock():
        data = load_vars()
        if not drop_all and not any(k.get("name") == key for k in data.get("tsig_keys") or []):
            raise ValidationError(f"no TSIG key named {key!r}")
        acls = {name: list(entries or []) for name, entries in (data.get("bind_acls") or {}).items()}
        for name in add:
            if not NAME_RE.match(name) or name in RESERVED:
                raise ValidationError(f"invalid ACL name {name!r}")
            entries = acls.setdefault(name, [])
            if not any(_is_key_entry(e, key) for e in entries):
                entries.append(f'key "{key}"')
        for name in (acls if drop_all else drop):
            if name not in acls:
                raise ValidationError(f"no ACL named {name!r}")
            acls[name] = [e for e in acls[name] if not _is_key_entry(e, key)]
        data["bind_acls"] = acls
        # The key's own `acls` list (from a vars file) is re-applied on every
        # render, so it must follow the same change.
        for k in data.get("tsig_keys") or []:
            if k.get("name") == key:
                own = [a for a in (k.get("acls") or []) if a not in drop and not drop_all]
                own += [a for a in add if a not in own]
                if own:
                    k["acls"] = own
                else:
                    k.pop("acls", None)
        save_vars(data)
    member = sorted(n for n, entries in acls.items() if any(_is_key_entry(e, key) for e in entries))
    if add or drop or drop_all:
        write_audit(actor, "TSIG_ACLS", f"key={key} add={list(add)} drop={'all' if drop_all else list(drop)}", source)
    return member
