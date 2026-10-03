import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request


def approle_login(v, creds_name):
    """Purpose: log in to OpenBao with one of fabric's stored AppRoles and get a short-lived token.
    Inputs:  v — vars dict: openbao_key_dir, plus what bao_request needs.
             creds_name — file name in openbao_key_dir (SETUP_CREDS or AGENT_CREDS): JSON {role_id, secret_id},
               root 0400, written by configure_openbao.
    Returns: the client token (str); its TTL is the role's (15 min, at most 30, set by configure_openbao).
    Fails:   ValidationError if the credentials file is missing (says to run `sudo fabricctl setup --step vault`),
             if OpenBao refuses the login (non-200), or from bao_request if OpenBao is unreachable;
             PermissionError (OSError) when not run as root; ValueError on bad JSON; KeyError if a field is absent.
    Feeds:   vault_status (AGENT_CREDS); setup/setup_openbao, secrets/common/read_vault_secrets and
             write_vault_secrets (SETUP_CREDS); tests/openbao/run.py.
    """
    path = os.path.join(v["openbao_key_dir"], creds_name)
    try:
        with open(path) as f:
            creds = json.load(f)
    except FileNotFoundError:
        raise ValidationError(f"{path} is missing: run `sudo fabricctl setup --step vault`")
    status, data = bao_request(v, "POST", "auth/approle/login",
                               body={"role_id": creds["role_id"], "secret_id": creds["secret_id"]})
    if status != 200:
        raise ValidationError(f"OpenBao refused the {creds_name} login: {data.get('errors') or status}")
    return data["auth"]["client_token"]
