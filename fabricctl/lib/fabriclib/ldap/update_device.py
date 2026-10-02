from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_device_fields import check_device_fields
from fabriclib.ldap.common.read_directory import read_directory
from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_UPDATE = r'''
d = IN
dn = "cn=%s,%s" % (d["name"], DEV)
owner = None
if d["owner"]:
    owner = "uid=%s,%s" % (d["owner"], USERS)
    try:
        c.search_s(owner, ldap.SCOPE_BASE, "(objectClass=*)", ["uid"])
    except ldap.NO_SUCH_OBJECT:
        raise Refused("no such user: " + d["owner"])
mods = [(ldap.MOD_REPLACE, "fabricDeviceType", [d["type"].encode()]),
        (ldap.MOD_REPLACE, "fabricEnabled", [b"TRUE" if d["enabled"] else b"FALSE"]),
        (ldap.MOD_REPLACE, "macAddress", [m.encode() for m in d["macs"]] or None),
        (ldap.MOD_REPLACE, "description", [d["description"].encode()] if d["description"] else None),
        (ldap.MOD_REPLACE, "owner", [owner.encode()] if owner else None)]
classes = s(c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["objectClass"])[0][1].get("objectClass"))
if "fabricdeviceroles" not in {x.lower() for x in classes}:
    mods.append((ldap.MOD_ADD, "objectClass", [b"fabricDeviceRoles"]))
mods.append((ldap.MOD_REPLACE, "fabricRoleName", [r.encode() for r in d["roles"]] or None))
c.modify_s(dn, mods)
out({"ok": True})
'''


def update_device(v, actor, name, fields, source="web"):
    """Purpose: Replace a device's type, MACs, owner, description, enabled flag and roles (fabricRoleName on
             the device; a device from before the directory split gains the fabricDeviceRoles class).
    Inputs:  v — fabric vars; actor — str, for the audit; name — an existing device; fields — same shape as
             add_device (check_device_fields); source — default "web".
    Returns: None.
    Fails:   ValidationError "no device named ..."; check_device_fields' messages; "no such user: <owner>"
             (from the directory);
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/devices/<name>) -> webui agentclient.save_device.
    Notes:   the roles are the device's own attribute, so no role entry is written. Audited as DEVICE_UPDATE.
    """
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    f = check_device_fields(fields, directory, name)
    run_dirsrv(v, _UPDATE, {"name": name, **f})
    write_audit(actor, "DEVICE_UPDATE", f"device={name} enabled={f['enabled']} type={f['type']} "
                                        f"macs={','.join(f['macs']) or '-'} roles={','.join(f['roles']) or '-'}",
                source)
