from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.check_device_fields import check_device_fields
from fabriclib.ldap.common.read_directory import read_directory
from fabriclib.ldap.common.run_dirsrv import run_dirsrv
from fabriclib.ldap.constants import DEVICE_NAME_RE

_ADD = r'''
d = IN
dn = "cn=%s,%s" % (d["name"], DEV)
attrs = {"objectClass": [b"top", b"device", b"ieee802Device", b"fabricDevice", b"fabricDeviceRoles"],
         "cn": [d["name"].encode()],
         "fabricDeviceType": [d["type"].encode()], "fabricEnabled": [b"TRUE" if d["enabled"] else b"FALSE"]}
if d["owner"]:
    owner = "uid=%s,%s" % (d["owner"], USERS)
    try:
        c.search_s(owner, ldap.SCOPE_BASE, "(objectClass=*)", ["uid"])
    except ldap.NO_SUCH_OBJECT:
        raise Refused("no such user: " + d["owner"])
    attrs["owner"] = [owner.encode()]
if d["macs"]:
    attrs["macAddress"] = [m.encode() for m in d["macs"]]
if d["description"]:
    attrs["description"] = [d["description"].encode()]
if d["roles"]:
    attrs["fabricRoleName"] = [r.encode() for r in d["roles"]]
c.add_s(dn, list(attrs.items()))
out({"ok": True})
'''


def add_device(v, actor, name, fields, source="web"):
    """Purpose: Add a device under ou=devices of the local suffix, naming its roles on the device
             (fabricRoleName).
    Inputs:  v — fabric vars; actor — str, for the audit; name — host-name label (stripped, lower-cased,
             DEVICE_NAME_RE); fields — {type, macs, owner (username), description, enabled (default True),
             roles} (check_device_fields); source — default "web".
    Returns: the normalised device name.
    Fails:   ValidationError "device name: a host name label — ..."; "device <name> already exists";
             check_device_fields' messages; "no such user: <owner>" (from the directory);
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/server.py Handler.directory (POST /v1/devices) -> webui agentclient.save_device.
    Notes:   runs as cn=device_admin; audited as DEVICE_ADD.
    """
    name = str(name).strip().lower()
    if not DEVICE_NAME_RE.match(name):
        raise ValidationError("device name: a host name label — lowercase letters, digits and '-'")
    directory = read_directory(v)
    if any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"device {name} already exists")
    f = check_device_fields(fields, directory, name)
    run_dirsrv(v, _ADD, {"name": name, **f})
    write_audit(actor, "DEVICE_ADD", f"device={name} type={f['type']} macs={','.join(f['macs']) or '-'} "
                                     f"roles={','.join(f['roles']) or '-'}", source)
    return name
