from fabriclib.directory.common.read_directory import read_directory
from fabriclib.directory.constants import DEVICE_TYPES, PERMISSIONS
from fabriclib.directory.list_devices import list_devices
from fabriclib.directory.list_roles import list_roles


def device_overview(v):
    """Purpose: Everything the Devices and Roles pages show, from one directory read.
    Inputs:  v — fabric vars (read_directory).
    Returns: {"devices": list_devices, "roles": list_roles, "types": DEVICE_TYPES, "permissions":
             {permission: [what it grants, what enforces it]}}.
    Fails:
             run_op's errors (ValidationError: the domain controller not reachable, or refusing).
    Feeds:   agent route GET /v1/devices (agent/ (fabric-agent) Handler.dispatch) -> webui
             agentclient.device_overview -> Devices, Roles and PKI pages.
    """
    directory = read_directory(v)
    return {"devices": list_devices(v, directory), "roles": list_roles(v, directory),
            "types": DEVICE_TYPES, "permissions": {k: list(p) for k, p in PERMISSIONS.items()}}
