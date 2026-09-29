import os

import yaml

from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import SECRETS_FILE
from fabriclib.secrets.common.read_vault_secrets import read_vault_secrets
from fabriclib.secrets.common.write_vault_secrets import write_vault_secrets
from fabriclib.secrets.secrets_in_openbao import secrets_in_openbao


def save_secrets(update, path=SECRETS_FILE, v=None):
    """Apply `update` to fabric's secrets where they live (see load_secrets):
    top-level keys are set, a None value removes a key, and `tsig_secrets`
    is merged key by key (a None secret removes that key). OpenBao gets a new
    version only if something changed (check-and-set against the version
    read). Returns the full, updated secrets."""
    in_vault = secrets_in_openbao(path) and not os.path.exists(path)
    if in_vault:
        v = v or load_vars(os.path.join(os.path.dirname(path), "vars.yaml"))
        current, version = read_vault_secrets(v)
    else:
        current, version = {}, 0
        if os.path.exists(path):
            with open(path) as f:
                current = yaml.safe_load(f) or {}
    new = dict(current)
    for key, value in update.items():
        if key == "tsig_secrets" and isinstance(value, dict):
            tsig = dict(new.get("tsig_secrets") or {})
            for name, secret in value.items():
                if secret is None:
                    tsig.pop(name, None)
                else:
                    tsig[name] = secret
            new["tsig_secrets"] = tsig
        elif value is None:
            new.pop(key, None)
        else:
            new[key] = value
    if new == current:
        return new
    if in_vault:
        write_vault_secrets(v, new, version)
        return new
    old = os.umask(0o077)
    try:
        with open(path, "w") as f:
            yaml.safe_dump(new, f, sort_keys=False)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    return new
