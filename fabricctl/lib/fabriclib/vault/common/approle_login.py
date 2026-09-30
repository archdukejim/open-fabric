import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request


def approle_login(v, creds_name):
    """Log in with an AppRole whose role_id/secret_id fabric stored in
    openbao_key_dir/<creds_name> (root, 0400). Returns a short-lived token."""
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
