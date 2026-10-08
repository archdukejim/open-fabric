from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.common.check_device_fields import check_device_fields
from fabriclib.directory.common.read_directory import read_directory
from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def update_device(v, actor, name, fields, source="web"):
    """Purpose: Replace a device's type, MACs, owner, description, enabled flag and roles (fabricRoleName on
             the device; a device from before the directory split gains the fabricDeviceRoles class).
    Inputs:  v — fabric vars; actor — str, for the audit; name — an existing device; fields — same shape as
             add_device (check_device_fields); source — default "web".
    Returns: None.
    Fails:   ValidationError "no device named ..."; check_device_fields' messages; "no such user: <owner>"
             (from the directory);
             run_op's errors (the directory unreachable, or refusing: e.g. another site's object).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/devices/<name>) -> webui agentclient.save_device.
    Notes:   the roles are the device's own attribute, so no role entry is written. Audited as DEVICE_UPDATE.
    """
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    f = check_device_fields(fields, directory, name)
    run_op(v, load_secrets(), "save_device", {"name": name, **f, "new": False})
    write_audit(actor, "DEVICE_UPDATE", f"device={name} enabled={f['enabled']} type={f['type']} "
                                        f"macs={','.join(f['macs']) or '-'} roles={','.join(f['roles']) or '-'}",
                source)
