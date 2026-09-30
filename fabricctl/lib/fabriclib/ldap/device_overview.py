from fabriclib.ldap.common.read_directory import read_directory
from fabriclib.ldap.constants import DEVICE_TYPES, PERMISSIONS
from fabriclib.ldap.list_devices import list_devices
from fabriclib.ldap.list_roles import list_roles


def device_overview(v):
    """Everything the Devices and Roles pages show, from one directory read:
    devices (with effective access), roles, and the RBAC vocabulary."""
    directory = read_directory(v)
    return {"devices": list_devices(v, directory), "roles": list_roles(v, directory),
            "types": DEVICE_TYPES, "permissions": {k: list(p) for k, p in PERMISSIONS.items()}}
