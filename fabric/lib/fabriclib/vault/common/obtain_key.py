import hmac

from fabriclib.vault.common.key_check_value import key_check_value
from fabriclib.vault.common.slot_type import slot_type


def obtain_key(v, store, key_id, only=None):
    """Try the slots (or just slot id `only`) for vault key version `key_id`.
    Returns (key, slot_id) from the first slot whose device is present and
    whose unwrapped key matches the stored check value; (None, None) if none
    can. Failures of one slot never stop the others."""
    expected = store["kcv"].get(key_id)
    for slot in store["slots"]:
        if only and slot["id"] != only:
            continue
        record = slot["wraps"].get(key_id)
        if not record:
            continue
        try:
            key = slot_type(slot["type"]).unwrap(v, slot, record)
        except Exception:           # a broken or absent device must not block the others
            key = None
        if key and expected and hmac.compare_digest(key_check_value(key, key_id), expected):
            return key, slot["id"]
    return None, None
