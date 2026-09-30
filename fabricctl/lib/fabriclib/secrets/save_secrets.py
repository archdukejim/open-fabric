import os

import yaml

from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import SECRETS_FILE
from fabriclib.secrets.common.read_vault_secrets import read_vault_secrets
from fabriclib.secrets.common.write_vault_secrets import write_vault_secrets
from fabriclib.secrets.secrets_in_openbao import secrets_in_openbao


def save_secrets(update, path=SECRETS_FILE, v=None):
    """Purpose: Apply a change to fabric's secrets where they live (as load_secrets decides).
    Inputs:  update — dict: top-level keys are set, a None value removes a key; tsig_secrets and
             radius_secrets are merged key by key (a None secret removes that key); path — the secrets
             file, default SECRETS_FILE; v — fabric vars for OpenBao, default from vars.yaml next to path.
    Returns: the full, updated secrets dict (unchanged content: nothing is written).
    Fails:   ValidationError from read_vault_secrets / write_vault_secrets (OpenBao unavailable, or a
             check-and-set conflict with a concurrent change); yaml.YAMLError; OSError.
    Feeds:   deploy.py apply_deployment, common/set_tsig_secrets, logs/run_logs_command,
             radius/add_radius_client, radius/remove_radius_client, radius/rotate_radius_secret,
             setup/collect_vars.
    Notes:   OpenBao gets a new version only when something changed. The file is rewritten in place with
             umask 077 and chmod 0600.
    """
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
        if key in ("tsig_secrets", "radius_secrets") and isinstance(value, dict):
            merged = dict(new.get(key) or {})
            for name, secret in value.items():
                if secret is None:
                    merged.pop(name, None)
                else:
                    merged[name] = secret
            new[key] = merged
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
