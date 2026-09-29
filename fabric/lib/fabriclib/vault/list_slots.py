from fabriclib.vault.common.read_slot_store import read_slot_store
from fabriclib.vault.common.slot_type import slot_type


def list_slots(v):
    """The unlock methods (key slots): [{id, type, label, device, present,
    key_id, added, detail, tested}] — never key material. `present` asks
    each type whether its device is here now (without unlocking anything)."""
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
