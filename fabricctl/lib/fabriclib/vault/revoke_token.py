from fabriclib.vault.common.bao_request import bao_request


def revoke_token(v, token):
    """Purpose: revoke a token (the initial root token once fabric's AppRoles exist, or a break-glass token) and check
             that it is dead.
    Inputs:  v — vars; token — the token to revoke (from a prompt or stdin, never argv).
    Returns: True if lookup-self with it now answers 403, else False.
    Fails:   ValidationError from bao_request if OpenBao is unreachable (the revoke call's own status is not checked).
    Feeds:   setup/setup_openbao, `fabricctl vault revoke-token` (run_vault_command), tests/openbao/run.py.
    Notes:   a new root token then needs the recovery keys (`fabricctl vault break-glass`).
    """
    bao_request(v, "POST", "auth/token/revoke-self", token=token)
    status, _ = bao_request(v, "GET", "auth/token/lookup-self", token=token)
    return status == 403
