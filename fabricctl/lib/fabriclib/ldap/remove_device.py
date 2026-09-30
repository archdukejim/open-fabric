from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.read_directory import read_directory
from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_REMOVE = r'''
dn = "cn=%s,%s" % (IN["name"], DEV)
for r in IN["roles"]:
    c.modify_s("cn=%s,%s" % (r, ROLES), [(ldap.MOD_DELETE, "member", [dn.encode()])])
c.delete_s(dn)
out({"ok": True})
'''


def remove_device(v, actor, name, source="web"):
    """Delete a device and take it out of every role. Certificates issued to
    it stay valid until they expire (revoke them separately)."""
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    roles = [r["name"] for r in directory["roles"] if name in r["members"]]
    run_dirsrv(v, _REMOVE, {"name": name, "roles": roles})
    write_audit(actor, "DEVICE_REMOVE", f"device={name}", source)
