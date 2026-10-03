from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type


def list_slots(v):
    """Purpose: list the unlock methods for the CLI and the web UI; never key material.
    Inputs:  v — vars; reads slots.json and asks each type whether its device is here now (no unlock, no PIN).
    Returns: [{id, type, label, device (summary or path), present, key_id, stale, added, detail, tested}]; key_id is
             the current version if the slot holds it, else the versions it holds; stale when it lacks the current
             one. [] before the first method.
    Fails:   ValidationError from slot_type for an unknown type in the store (the whole list fails); errors from a
             type's present() are caught (present False).
    Feeds:   agent route GET /v1/vault/slots (web UI), `fabricctl vault slots` (run_vault_command),
             tests/openbao/run.py.
    """
    store = read_slot_store(v)
    if not store:
        return []
    out = []
    for slot in store["slots"]:
        mod = slot_type(slot["type"])
        try:
            here = bool(mod.present(v, slot))
        except Exception:
            here = False
        device = slot.get("device") or {}
        out.append({"id": slot["id"], "type": slot["type"], "label": slot.get("label", ""),
                    "device": device.get("summary") or device.get("path") or "",
                    "present": here, "key_id": store["key_id"] if store["key_id"] in slot["wraps"] else
                    ", ".join(sorted(slot["wraps"])) or "—",
                    "stale": store["key_id"] not in slot["wraps"],
                    "added": slot.get("added", ""), "detail": device.get("detail", ""), "tested": mod.TESTED})
    return out
