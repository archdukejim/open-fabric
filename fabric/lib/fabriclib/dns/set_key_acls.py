import re

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.add_acl_entries import NAME_RE, RESERVED


def _is_key_entry(entry, key):
    return re.fullmatch(rf'!?key\s+"?{re.escape(key)}"?', str(entry).strip()) is not None


def set_key_acls(actor, key, add=(), drop=(), drop_all=False, source="cli"):
    """Assign TSIG key `key` to ACLs (`key "<name>"` entries; a missing ACL
    is created) and/or take it out of ACLs — of every ACL with drop_all,
    which removing a key needs: BIND refuses a config whose ACL names an
    undefined key. Run apply afterwards. Returns the ACLs holding the key."""
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
