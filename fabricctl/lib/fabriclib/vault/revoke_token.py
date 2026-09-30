from fabriclib.vault.common.bao_request import bao_request


def revoke_token(v, token):
    """Revoke a token (used for the initial root token once fabric's own
    AppRoles exist). A new root token needs the recovery keys
    (`fabricctl vault break-glass`). Returns True if it is now invalid."""
    bao_request(v, "POST", "auth/token/revoke-self", token=token)
    status, _ = bao_request(v, "GET", "auth/token/lookup-self", token=token)
    return status == 403
