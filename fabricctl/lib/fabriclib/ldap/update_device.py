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
c.modify_s(dn, mods)
for r in d["add_roles"]:
    c.modify_s("cn=%s,%s" % (r, ROLES), [(ldap.MOD_ADD, "member", [dn.encode()])])
for r in d["drop_roles"]:
    c.modify_s("cn=%s,%s" % (r, ROLES), [(ldap.MOD_DELETE, "member", [dn.encode()])])
out({"ok": True})
'''


def update_device(v, actor, name, fields, source="web"):
    """Purpose: Replace a device's type, MACs, owner, description, enabled flag and role memberships.
    Inputs:  v — fabric vars; actor — str, for the audit; name — an existing device; fields — same shape as
             add_device (check_device_fields); source — default "web".
    Returns: None.
    Fails:   ValidationError "no device named ..."; check_device_fields' messages; "no such user: <owner>"
             (from the directory);
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/server.py Handler.directory (POST /v1/devices/<name>) -> webui agentclient.save_device.
    Notes:   only role memberships that change are touched. Audited as DEVICE_UPDATE.
    """
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    f = check_device_fields(fields, directory, name)
    current = {r["name"] for r in directory["roles"] if name in r["members"]}
    run_dirsrv(v, _UPDATE, {"name": name, **f, "add_roles": sorted(set(f["roles"]) - current),
                            "drop_roles": sorted(current - set(f["roles"]))})
    write_audit(actor, "DEVICE_UPDATE", f"device={name} enabled={f['enabled']} type={f['type']} "
                                        f"macs={','.join(f['macs']) or '-'} roles={','.join(f['roles']) or '-'}",
                source)
