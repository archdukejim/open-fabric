import base64

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.bao_request import bao_request


def _decode(encoded, otp):
    raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4))
    return bytes(a ^ b for a, b in zip(raw, otp.encode())).decode()


def generate_root_token(v, actor, recovery_keys, restart=False, source="cli"):
    """Break glass: a new root token from the recovery keys, for when nobody
    can sign in (Keycloak down, a policy locked everyone out). Uses
    OpenBao's generate-root over the break-glass socket (host root only),
    with a one-time pad so the token is never sent in clear. Refuses to take
    over someone else's attempt unless `restart`. The caller shows the token once; it must be revoked after use
    (`fabricctl vault revoke-token`). Audited on the host and in OpenBao."""
    st, att = bao_request(v, "GET", "sys/generate-root/attempt", admin=True)
    if st != 200:
        raise ValidationError(f"OpenBao is not reachable or sealed ({st})")
    if att.get("started"):
        if not restart:
            raise ValidationError("a root-token attempt is already in progress (use --restart to cancel it)")
        bao_request(v, "DELETE", "sys/generate-root/attempt", admin=True)
    st, att = bao_request(v, "POST", "sys/generate-root/attempt", body={}, admin=True)
    if st != 200 or not att.get("otp"):
        raise ValidationError(f"could not start the root-token attempt: {att.get('errors') or st}")
    nonce, otp, result = att["nonce"], att["otp"], {}
    try:
        for key in recovery_keys:
            st, result = bao_request(v, "POST", "sys/generate-root/update",
                                     body={"key": key.strip(), "nonce": nonce}, admin=True)
            if st != 200:
                raise ValidationError(f"recovery key refused: {result.get('errors') or st}")
            if result.get("complete"):
                break
        if not result.get("complete"):
            raise ValidationError(f"{result.get('progress', 0)} of {result.get('required', '?')} recovery keys given")
    except ValidationError:
        bao_request(v, "DELETE", "sys/generate-root/attempt", admin=True)
        write_audit(actor, "VAULT_BREAK_GLASS", "FAILED", source)
        raise
    token = _decode(result["encoded_token"], otp)
    if bao_request(v, "GET", "auth/token/lookup-self", token=token)[0] != 200:
        raise ValidationError("the decoded root token does not work")
    write_audit(actor, "VAULT_BREAK_GLASS", "root token created from the recovery keys (revoke it after use)", source)
    return token
