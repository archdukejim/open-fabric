import hmac

from fabriclib.vault.common.key_check_value import key_check_value
from fabriclib.vault.common.slot_type import slot_type


def obtain_key(v, store, key_id, only=None, attended=False, errors=None):
    """Purpose: get vault key version key_id from the unlock methods: the first slot whose key verifies wins.
    Inputs:  v — vars; store — the slot store (read_slot_store); key_id — the key version wanted;
             only — a slot id to try just that one (None: all, in store order);
             attended — a person asked for this (a security key that saw a wrong PIN may then be tried;
               unattended starts do not spend a PIN try on it);
             errors — a list collecting "<slot id>: <reason>" for each failing slot, or None.
    Returns: (key bytes, slot id), or (None, None) when no slot gives a key matching kcv[key_id]
             (with no stored check value for key_id no key is accepted).
    Fails:   never for a slot's failure — every exception from a slot type is caught (and recorded in errors);
             KeyError only for a store without "kcv" or "slots".
    Feeds:   unlock_vault, test_slot, remove_slot, rotate_vault_key, add_usb_slot, add_kmip_slot,
             add_security_key_slot, tests/openbao/run.py.
    Notes:   a broken or absent device must never block the others. Keys are compared in constant time.
    """
    expected = store["kcv"].get(key_id)
    for slot in store["slots"]:
        if only and slot["id"] != only:
            continue
        record = slot["wraps"].get(key_id)
        if not record:
            continue
        try:
            key = slot_type(slot["type"]).unwrap(v, slot, record, attended)
        except Exception as exc:    # a broken or absent device must not block the others
            key = None
            if errors is not None:
                errors.append(f"{slot['id']}: {exc}")
        if key and expected and hmac.compare_digest(key_check_value(key, key_id), expected):
            return key, slot["id"]
        if key and errors is not None:
            errors.append(f"{slot['id']}: unwrapped a key that does not match the check value")
    return None, None
