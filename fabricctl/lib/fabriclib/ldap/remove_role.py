from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_REMOVE = r'''
dn = "cn=%s,%s" % (IN["name"], ROLES)
members = c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["member"])[0][1].get("member", [])
if members:
    raise Refused("role %s still has %d device(s); take them out first" % (IN["name"], len(members)))
c.delete_s(dn)
out({"ok": True})
'''


def remove_role(v, actor, name, source="web"):
    """Delete a device role. Refused while devices are still in it, so no
    device silently loses (or keeps) access."""
    if not ROLE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid role name: {name!r}")
    run_dirsrv(v, _REMOVE, {"name": name})
    write_audit(actor, "ROLE_REMOVE", f"role={name}", source)
