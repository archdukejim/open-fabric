from fabriclib.common.errors import ValidationError
from fabriclib.secrets.constants import VAULT_PATH
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import SETUP_CREDS


def read_vault_secrets(v, token=None):
    """Purpose: Read fabric's secrets and their version from OpenBao (KV v2 fabric/secrets).
    Inputs:  v — fabric vars for OpenBao (openbao_key_dir, ip_openbao, hostname_openbao, root CA);
             token — OpenBao token, default a fresh AppRole login with SETUP_CREDS (setup-approle.json).
    Returns: (secrets dict, version int); ({}, 0) if the entry does not exist yet.
    Fails:   ValidationError "reading fabric's secrets from OpenBao failed: ..." for any other status
             (sealed, denied);
             approle_login's ValidationError ("<path> is missing: run ...", "OpenBao refused the
             setup-approle.json login: ..."); bao_request's "OpenBao is not reachable at ...".
             Never an empty result for an unreachable or sealed OpenBao.
    Feeds:   load_secrets, save_secrets, import_secrets.
    """
    token = token or approle_login(v, SETUP_CREDS)
    mount, _, name = VAULT_PATH.partition("/")
    status, data = bao_request(v, "GET", f"{mount}/data/{name}", token=token)
    if status == 404:
        return {}, 0
    if status != 200:
        raise ValidationError(f"reading fabric's secrets from OpenBao failed: {data.get('errors') or status}")
    return data["data"]["data"] or {}, int(data["data"]["metadata"]["version"])
