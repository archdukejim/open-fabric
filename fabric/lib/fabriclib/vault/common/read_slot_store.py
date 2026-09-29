import json
import os

from fabriclib.vault.constants import SLOT_STORE


def read_slot_store(v):
    """The unlock-method (key slot) store, or None before the first one exists.

    {"format": 1, "key_id": current vault key version, "previous_key_id": set
     only during a rotation, "kcv": {key_id: check value}, "slots": [{id, type,
     label, added, device: {...}, wraps: {key_id: type-specific}}], "mac": ...}"""
    path = os.path.join(v["openbao_key_dir"], SLOT_STORE)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)
