from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.vault.common.obtain_key import obtain_key
from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type
from fabriclib.vault.common.write_slot_store import write_slot_store
from fabriclib.vault.write_device_rules import write_device_rules


def remove_slot(v, actor, slot_id, source="web"):
    """Remove an unlock method. Refused for the last one, and unless another
    method is present to vouch for the change (the store is re-signed with
    the vault key). The removed method's copy is destroyed where fabric can
    (a local file is shredded); a USB stick's copy stays readable on the
    stick until the key is rotated."""
    store = read_slot_store(v)
    slots = store["slots"] if store else []
    target = next((s for s in slots if s["id"] == slot_id), None)
    if target is None:
        raise ValidationError(f"no unlock method {slot_id!r}")
    rest = [s for s in slots if s["id"] != slot_id and store["key_id"] in s["wraps"]]
    if not rest:
        raise ValidationError("the last working unlock method cannot be removed")
    key = None
    for s in rest:
        key, _ = obtain_key(v, store, store["key_id"], only=s["id"])
        if key:
            break
    if key is None:
        raise ValidationError("plug in another unlock method first: removing one needs a remaining one present")
    mod = slot_type(target["type"])
    for record in target["wraps"].values():
        if hasattr(mod, "forget"):
            mod.forget(v, target, record)
    store["slots"] = [s for s in slots if s["id"] != slot_id]
    write_slot_store(v, store, key)
    write_device_rules(v)
    write_audit(actor, "VAULT_SLOT_REMOVE", f"slot={slot_id} type={target['type']}", source)
