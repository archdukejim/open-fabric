import hashlib
import hmac
import json


def slot_store_mac(store, key):
    """Purpose: sign the slot store with the vault key, so a store changed while the host was off does not verify.
    Inputs:  store — slot store dict (its own "mac" field is left out); key — the current vault key (bytes).
    Returns: hex HMAC-SHA256 over the store as canonical JSON (sorted keys, no spaces).
    Fails:   TypeError if the store holds a value JSON cannot encode.
    Feeds:   write_slot_store (stores it), unlock_vault (compares it and audits a mismatch).
    """
    body = json.dumps({k: v for k, v in store.items() if k != "mac"}, sort_keys=True, separators=(",", ":"))
    return hmac.new(key, body.encode(), hashlib.sha256).hexdigest()
