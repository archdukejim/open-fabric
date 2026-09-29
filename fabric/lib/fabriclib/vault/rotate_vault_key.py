import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.key_check_value import key_check_value
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type
from fabriclib.vault.common.write_seal_config import write_seal_config
from fabriclib.vault.common.write_slot_store import write_slot_store
from fabriclib.vault.unlock_vault import unlock_vault
from fabriclib.vault.wipe_runtime_keys import wipe_runtime_keys


def _next_id(key_id):
    stem, _, n = key_id.rpartition("-")
    return f"{stem}-{int(n) + 1}" if n.isdigit() else f"{key_id}-2"


def rotate_vault_key(v, actor, restart, source="web"):
    """New vault key; every unlock method whose device is present now gets it,
    the others are dropped (the answer to a lost stick or token).

    OpenBao moves over with its static seal's key rotation: restart with the
    new key as current and the old as previous (OpenBao re-wraps itself),
    then restart with only the new one. `restart()` restarts OpenBao and
    waits until it is unsealed (raises otherwise). The store is saved in a
    state that can unlock both keys before anything restarts, so an
    interruption never leaves the vault without a way in."""
    store = read_slot_store(v)
    if not store or store.get("previous_key_id"):
        raise ValidationError("no vault key, or a rotation is already in progress")
    old_id = store["key_id"]
    old, _ = obtain_key(v, store, old_id)
    if old is None:
        raise ValidationError("no unlock method is present: plug one in to rotate")
    new, new_id = os.urandom(32), _next_id(old_id)
    kept, dropped = [], []
    for slot in store["slots"]:
        mod = slot_type(slot["type"])
        key, _ = obtain_key(v, store, old_id, only=slot["id"])
        if key is None:
            dropped.append(slot["id"])
            continue
        slot["wraps"][new_id] = mod.wrap(v, slot, new, new_id)
        kept.append(slot)
    store.update(slots=kept, key_id=new_id, previous_key_id=old_id)
    store["kcv"][new_id] = key_check_value(new, new_id)
    write_slot_store(v, store, new)                 # both keys reachable from here on
    write_seal_config(v, new_id, old_id)
    unlock_vault(v)
    restart()                                       # OpenBao re-wraps its root key with the new key
    for slot in kept:
        record = slot["wraps"].pop(old_id, None)
        mod = slot_type(slot["type"])
        if record and hasattr(mod, "forget"):
            mod.forget(v, slot, record)
    store.update(previous_key_id=None)
    store["kcv"].pop(old_id, None)
    write_slot_store(v, store, new)
    write_seal_config(v, new_id)
    unlock_vault(v)
    restart()                                       # proves the new key alone opens the vault
    wipe_runtime_keys(v)
    write_audit(actor, "VAULT_ROTATE", f"{old_id} -> {new_id}; kept={','.join(s['id'] for s in kept)} "
                                       f"dropped={','.join(dropped) or '-'}", source)
    return {"key_id": new_id, "kept": [s["id"] for s in kept], "dropped": dropped}
