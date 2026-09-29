import hashlib
import hmac


def key_check_value(key, key_id):
    """A short fingerprint of vault key `key` (version `key_id`) that proves a
    slot unwrapped the right key without revealing anything about it:
    HMAC-SHA256(key, "fabric-kcv:" + key_id), first 16 bytes, hex."""
    return hmac.new(key, f"fabric-kcv:{key_id}".encode(), hashlib.sha256).hexdigest()[:32]
