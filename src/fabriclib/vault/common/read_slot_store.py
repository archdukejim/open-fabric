import json
import os

from fabriclib.vault.constants import SLOT_STORE


def read_slot_store(v):
    """Purpose: read the unlock-method (key slot) store.
    Inputs:  v — vars: openbao_key_dir; reads <openbao_key_dir>/slots.json (root 0600).
    Returns: the store dict, or None before the first unlock method exists. Shape: {"format": 1,
             "key_id": current key version, "previous_key_id": set only during a rotation,
             "kcv": {key_id: check value}, "slots": [{id, type, label, added, device: {...},
             wraps: {key_id: type-specific record}}], "mac": signature}.
    Fails:   PermissionError (OSError) when not root; ValueError if the file is not valid JSON.
             The signature is not checked here (unlock_vault does that).
    Feeds:   ensure_vault_key, unlock_vault, list_slots, test_slot, remove_slot, rotate_vault_key, add_usb_slot,
             add_kmip_slot, add_security_key_slot, vault_device_event, write_device_rules, vault_status._key_state,
             tests/openbao/run.py.
    """
    path = os.path.join(v["openbao_key_dir"], SLOT_STORE)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
