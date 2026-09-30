import json
import os

from fabriclib.vault.common.slot_store_mac import slot_store_mac
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import SLOT_STORE


def write_slot_store(v, store, key):
    """Save the slot store (root, 0600) signed with the current vault key."""
    store = dict(store, format=1)
    store["mac"] = slot_store_mac(store, key)
    os.makedirs(v["openbao_key_dir"], mode=0o700, exist_ok=True)
    write_private_file(os.path.join(v["openbao_key_dir"], SLOT_STORE), json.dumps(store, indent=2) + "\n", 0, 0, 0o600)
    return store
