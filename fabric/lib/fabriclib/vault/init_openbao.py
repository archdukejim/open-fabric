import time

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request


def init_openbao(v):
    """Initialise OpenBao once. With the static seal it unseals itself;
    init returns *recovery* keys (needed to generate a new root token or
    migrate the seal) and the initial root token. Returns
    {"recovery_keys": [...], "root_token": ...}, or None when OpenBao was
    already initialised."""
    status, data = bao_request(v, "GET", "sys/init")
    if status != 200:
        raise ValidationError(f"OpenBao init status failed: {data.get('errors') or status}")
    if data.get("initialized"):
        return None
    shares = int(v.get("openbao_recovery_shares", 1))
    threshold = int(v.get("openbao_recovery_threshold", 1))
    status, data = bao_request(v, "PUT", "sys/init",
                               body={"recovery_shares": shares, "recovery_threshold": threshold}, timeout=120)
    if status != 200:
        raise ValidationError(f"OpenBao init failed: {data.get('errors') or status}")
    # Init returns before the node has unsealed and become Raft leader; until
    # then requests fail with "internal error". sys/health says 200 = active.
    deadline = time.time() + 120
    while bao_request(v, "GET", "sys/health")[0] != 200:
        if time.time() > deadline:
            raise ValidationError("OpenBao did not become active within 2 minutes of init")
        time.sleep(2)
    return {"recovery_keys": data.get("recovery_keys_b64") or data.get("recovery_keys") or [],
            "root_token": data["root_token"]}
