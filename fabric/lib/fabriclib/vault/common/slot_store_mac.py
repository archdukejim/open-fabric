import hashlib
import hmac
import json


def slot_store_mac(store, key):
    """HMAC-SHA256 of the slot store (without its own "mac"), keyed with the
    vault key: a store changed while the host was off does not verify."""
    body = json.dumps({k: v for k, v in store.items() if k != "mac"}, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
