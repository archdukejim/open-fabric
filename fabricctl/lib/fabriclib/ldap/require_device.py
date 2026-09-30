from fabriclib.common.errors import ValidationError
from fabriclib.ldap.common.read_directory import read_directory


def require_device(v, name):
    """Refuse unless device `name` exists (checked before a certificate is
    issued for it, so no certificate ends up issued but unlinked)."""
    if not any(d["name"] == name for d in read_directory(v)["devices"]):
        raise ValidationError(f"no device named {name!r}")
