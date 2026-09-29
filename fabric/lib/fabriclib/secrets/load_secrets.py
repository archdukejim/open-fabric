import os

import yaml

from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import SECRETS_FILE
from fabriclib.secrets.common.read_vault_secrets import read_vault_secrets
from fabriclib.secrets.secrets_in_openbao import secrets_in_openbao


def load_secrets(path=SECRETS_FILE, v=None):
    """fabric's secrets, wherever they live.

    Before the import into OpenBao: the 0600 file at `path` ({} if absent).
    After it (marker present): OpenBao — unless a secrets file was put back
    (a reinstall restores one), which is then used and re-imported by the
    `vault` step. OpenBao unreachable or sealed raises ValidationError: a
    missing file must never look like "no secrets", which would make setup
    generate new passwords that the running services do not know."""
    if os.path.exists(path) or not secrets_in_openbao(path):
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return yaml.safe_load(f) or {}
    return read_vault_secrets(v or load_vars(os.path.join(os.path.dirname(path), "vars.yaml")))[0]
