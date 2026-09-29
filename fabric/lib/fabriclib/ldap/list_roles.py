from fabriclib.ldap.common.read_directory import read_directory


def list_roles(v, directory=None):
    """Device roles, lowest priority number first, with their member devices."""
    directory = directory or read_directory(v)
    return sorted(directory["roles"], key=lambda r: (r["priority"], r["name"]))
