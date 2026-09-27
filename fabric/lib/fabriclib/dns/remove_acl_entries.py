from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.builtin_acls import builtin_acls


def remove_acl_entries(actor, acl, entries=None, source="cli"):
    """Remove entries from a BIND ACL, or the whole ACL when `entries` is
    empty. Built-in ACLs and their built-in entries stay (they are rendered
    on every apply). Run apply afterwards."""
    with vars_lock():
        data = load_vars()
        acls = dict(data.get("bind_acls") or {})
        if acl not in acls:
            raise ValidationError(f"no ACL named {acl!r}")
        builtin = builtin_acls(data)
        if not entries:
            if acl in builtin:
                raise ValidationError(f"{acl!r} is built in; remove its added entries instead")
            del acls[acl]
            policies = dict(data.get("bind_acl_policies") or {})
            policies.pop(acl, None)
            data["bind_acl_policies"] = policies
        else:
            kept = list(acls[acl])
            for entry in entries:
                match = next((e for e in kept if e.replace('"', "") == str(entry).replace('"', "").strip()), None)
                if match is None:
                    raise ValidationError(f"{entry!r} is not in {acl!r}")
                if match in builtin.get(acl, []):
                    raise ValidationError(f"{entry!r} is a built-in entry of {acl!r}")
                kept.remove(match)
            acls[acl] = kept
        data["bind_acls"] = acls
        save_vars(data)
    write_audit(actor, "ACL_REMOVE", f"acl={acl} entries={list(entries or []) or 'all'}", source)
