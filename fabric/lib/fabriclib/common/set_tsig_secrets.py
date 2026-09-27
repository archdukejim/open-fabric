import os

import yaml

from fabriclib.common.paths import SECRETS_FILE


def set_tsig_secrets(updates, path=SECRETS_FILE):
    """Set ({name: secret}) or remove ({name: None}) TSIG secrets in the
    secrets file, keeping it 0600. Other secrets are untouched."""
    secrets = {}
    if os.path.exists(path):
        with open(path) as f:
            secrets = yaml.safe_load(f) or {}
    tsig = secrets.setdefault("tsig_secrets", {}) or {}
    for name, secret in updates.items():
        if secret is None:
            tsig.pop(name, None)
        else:
            tsig[name] = secret
    secrets["tsig_secrets"] = tsig
    old = os.umask(0o077)
    try:
        with open(path, "w") as f:
            yaml.safe_dump(secrets, f, sort_keys=False)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
