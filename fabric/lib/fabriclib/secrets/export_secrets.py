import os

import yaml

from fabriclib.secrets.load_secrets import load_secrets
from fabriclib.vault.common.write_private_file import write_private_file


def export_secrets(secrets_file, dest, v=None):
    """Write fabric's secrets (from wherever they live) to `dest`, root-only
    0600 — for a reinstall's backup, which setup re-imports and shreds.
    Returns dest."""
    os.makedirs(os.path.dirname(dest), mode=0o700, exist_ok=True)
    write_private_file(dest, yaml.safe_dump(load_secrets(secrets_file, v), sort_keys=False), 0, 0, 0o600)
    return dest
