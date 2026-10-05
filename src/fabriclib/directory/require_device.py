from fabriclib.common.errors import ValidationError
from fabriclib.directory.common.read_directory import read_directory


def require_device(v, name):
    """Purpose: Refuse unless a device exists, checked before a certificate is issued for it so none ends up
             issued but unlinked.
    Inputs:  v — fabric vars; name — device name.
    Returns: None.
    Fails:   ValidationError "no device named ..."; read_directory's /
             run_op's errors (ValidationError: the domain controller not reachable, or refusing).
    Feeds:   pki/issue_key_pair, pki/sign_csr.
    """
    if not any(d["name"] == name for d in read_directory(v)["devices"]):
        raise ValidationError(f"no device named {name!r}")
