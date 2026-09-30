
from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.bao_request import bao_request
from fabriclib.vault.common.wait_active import wait_active


def init_openbao(v):
    """Purpose: initialise OpenBao once, then wait until it is the active node.
    Inputs:  v — vars: openbao_recovery_shares (1), openbao_recovery_threshold (1).
    Returns: {"recovery_keys": [base64 str], "root_token": str} on the first init; None if already initialised.
    Fails:   ValidationError if sys/init cannot be read or init is refused; from wait_active if OpenBao is not active
             within 120 s; from bao_request if unreachable; KeyError if the answer has no root_token.
    Feeds:   setup/setup_openbao, tests/openbao/run.py.
    Notes:   with the static seal OpenBao unseals itself; init returns *recovery* keys (needed to generate a new root
             token or migrate the seal). Init returns before the node is unsealed and Raft leader; until then
             requests fail with "internal error", hence the wait.
    """
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
    wait_active(v)
    return {"recovery_keys": data.get("recovery_keys_b64") or data.get("recovery_keys") or [],
            "root_token": data["root_token"]}
