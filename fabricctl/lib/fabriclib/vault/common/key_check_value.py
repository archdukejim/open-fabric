import hashlib
import hmac


def key_check_value(key, key_id):
    """Purpose: fingerprint a vault key so an unwrapped key can be verified without storing anything that reveals it.
    Inputs:  key — the key (bytes); key_id — its version name (str), e.g. "fabric-1".
    Returns: 32 hex characters: the first 16 bytes of HMAC-SHA256(key, "fabric-kcv:" + key_id).
    Fails:   never — pure computation (TypeError only if key is not bytes).
    Feeds:   obtain_key (compares it), ensure_vault_key and rotate_vault_key (store it as kcv[key_id]).
    """
    return hmac.new(key, f"fabric-kcv:{key_id}".encode(), hashlib.sha256).hexdigest()[:32]
