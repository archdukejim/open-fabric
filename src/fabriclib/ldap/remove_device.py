from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.ldap.common.read_directory import read_directory
from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_REMOVE = r'''
c.delete_s("cn=%s,%s" % (IN["name"], DEV))
out({"ok": True})
'''


def remove_device(v, actor, name, source="web"):
    """Purpose: Delete a device (its roles go with it: they are the device's own attribute).
    Inputs:  v — fabric vars; actor — str, for the audit; name — an existing device; source — default "web".
    Returns: None.
    Fails:   ValidationError "no device named ...";
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/devices/<name>/delete) -> webui
             agentclient.delete_device.
    Notes:   certificates issued to it stay valid until they expire (revoke them separately). Audited as
             DEVICE_REMOVE.
    """
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    run_dirsrv(v, _REMOVE, {"name": name})
    write_audit(actor, "DEVICE_REMOVE", f"device={name}", source)
