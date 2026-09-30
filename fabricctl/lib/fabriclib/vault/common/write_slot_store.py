import json
import os

from fabriclib.vault.common.slot_store_mac import slot_store_mac
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import SLOT_STORE


def write_slot_store(v, store, key):
    """Purpose: save the slot store root-only (0600), signed with the current vault key.
    Inputs:  v — vars: openbao_key_dir (made 0700 if missing); store — store dict (format and mac are set here);
             key — the current vault key (bytes) to sign with.
    Returns: the store as saved: a copy with format=1 and its mac.
    Fails:   OSError from makedirs or write_private_file (e.g. not root); TypeError if the store is not JSON-able.
    Feeds:   ensure_vault_key, add_usb_slot, add_kmip_slot, add_security_key_slot, remove_slot, rotate_vault_key
             (none uses the return value).
    """
    store = dict(store, format=1)
    store["mac"] = slot_store_mac(store, key)
    os.makedirs(v["openbao_key_dir"], mode=0o700, exist_ok=True)
    write_private_file(os.path.join(v["openbao_key_dir"], SLOT_STORE), json.dumps(store, indent=2) + "\n", 0, 0, 0o600)
    return store
