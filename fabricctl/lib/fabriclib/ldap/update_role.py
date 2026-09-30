from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_role_fields import check_role_fields
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_UPDATE = r'''
r = IN
c.modify_s("cn=%s,%s" % (r["name"], ROLES), [
    (ldap.MOD_REPLACE, "description", [r["description"].encode()] if r["description"] else None),
    (ldap.MOD_REPLACE, "fabricPermission", [p.encode() for p in r["permissions"]] or None),
    (ldap.MOD_REPLACE, "fabricVlan", [str(r["vlan"]).encode()] if r["vlan"] else None),
    (ldap.MOD_REPLACE, "fabricPriority", [str(r["priority"]).encode()])])
out({"ok": True})
'''


def update_role(v, actor, name, fields, source="web"):
    """Replace a role's description, permissions, VLAN and priority. Members
    are managed from each device."""
    if not ROLE_NAME_RE.match(str(name)):
        raise ValidationError(f"invalid role name: {name!r}")
    f = check_role_fields(fields)
    run_dirsrv(v, _UPDATE, {"name": name, **f})
    write_audit(actor, "ROLE_UPDATE", f"role={name} permissions={','.join(f['permissions']) or '-'} "
                                      f"vlan={f['vlan'] or '-'} priority={f['priority']}", source)
