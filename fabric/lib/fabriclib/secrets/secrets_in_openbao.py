import os

from fabriclib.secrets.constants import MARKER


def secrets_in_openbao(secrets_file):
    """True once fabric's secrets were imported into OpenBao: the marker file
    next to the (then removed) secrets file says so. From then on a missing
    secrets file never means "no secrets"."""
    return os.path.exists(os.path.join(os.path.dirname(secrets_file), MARKER))
