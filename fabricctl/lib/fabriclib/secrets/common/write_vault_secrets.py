from fabriclib.common.errors import ValidationError
from fabriclib.secrets.constants import VAULT_PATH
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.constants import SETUP_CREDS


def write_vault_secrets(v, secrets, version, token=None):
    """Write fabric's secrets as a new KV v2 version, only if the stored
    version is still `version` (check-and-set: a concurrent change is
    refused, never overwritten). Returns the new version."""
    token = token or approle_login(v, SETUP_CREDS)
    mount, _, name = VAULT_PATH.partition("/")
    status, data = bao_request(v, "POST", f"{mount}/data/{name}", token=token,
                               body={"options": {"cas": int(version)}, "data": secrets})
    if status != 200:
        raise ValidationError(f"writing fabric's secrets to OpenBao failed: {data.get('errors') or status}")
    return int(data["data"]["version"])
