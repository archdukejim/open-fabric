from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.common.read_directory import read_directory
from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def remove_device(v, actor, name, source="web"):
    """Purpose: Delete a device (its roles go with it: they are the device's own attribute).
    Inputs:  v — fabric vars; actor — str, for the audit; name — an existing device; source — default "web".
    Returns: None.
    Fails:   ValidationError "no device named ...";
             run_op's errors (the directory unreachable, or refusing: e.g. another site's object).
    Feeds:   agent/ (fabric-agent) Handler.directory (POST /v1/devices/<name>/delete) -> webui
             agentclient.delete_device.
    Notes:   certificates issued to it stay valid until they expire (revoke them separately). Audited as
             DEVICE_REMOVE.
    """
    directory = read_directory(v)
    if not any(d["name"] == name for d in directory["devices"]):
        raise ValidationError(f"no device named {name!r}")
    run_op(v, load_secrets(), "remove_device", {"name": name})
    write_audit(actor, "DEVICE_REMOVE", f"device={name}", source)
