from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_role_fields import check_role_fields
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import ROLE_NAME_RE

_ADD = r'''
r = IN
attrs = {"objectClass": [b"top", b"groupOfNames", b"fabricRole"], "cn": [r["name"].encode()],
         "fabricPriority": [str(r["priority"]).encode()]}
if r["description"]:
    attrs["description"] = [r["description"].encode()]
if r["permissions"]:
    attrs["fabricPermission"] = [p.encode() for p in r["permissions"]]
if r["vlan"]:
    attrs["fabricVlan"] = [str(r["vlan"]).encode()]
c.add_s("cn=%s,%s" % (r["name"], ROLES), list(attrs.items()))
out({"ok": True})
'''


def add_role(v, actor, name, fields, source="web"):
    """Create a device role: permissions it grants its member devices, an
    optional VLAN, a priority (lower wins when roles set different VLANs)."""
    name = str(name).strip().lower()
    if not ROLE_NAME_RE.match(name):
        raise ValidationError("role name: lowercase letters, digits, '-' and '_'")
    f = check_role_fields(fields)
    run_dirsrv(v, _ADD, {"name": name, **f})
    write_audit(actor, "ROLE_ADD", f"role={name} permissions={','.join(f['permissions']) or '-'} "
                                   f"vlan={f['vlan'] or '-'} priority={f['priority']}", source)
    return name
