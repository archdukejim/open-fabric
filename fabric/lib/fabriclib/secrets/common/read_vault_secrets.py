from fabriclib.common.errors import ValidationError
from fabriclib.secrets.constants import VAULT_PATH
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import SETUP_CREDS


def read_vault_secrets(v, token=None):
    """fabric's secrets from OpenBao as (dict, version); ({}, 0) if the entry
    does not exist yet. Unreachable or sealed OpenBao raises ValidationError —
    never an empty result."""
    token = token or approle_login(v, SETUP_CREDS)
    mount, _, name = VAULT_PATH.partition("/")
    status, data = bao_request(v, "GET", f"{mount}/data/{name}", token=token)
    if status == 404:
        return {}, 0
    if status != 200:
        raise ValidationError(f"reading fabric's secrets from OpenBao failed: {data.get('errors') or status}")
    return data["data"]["data"] or {}, int(data["data"]["metadata"]["version"])
