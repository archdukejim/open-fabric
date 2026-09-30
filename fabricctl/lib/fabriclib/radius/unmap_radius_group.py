from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def unmap_radius_group(actor, group, source="cli"):
    """Stop a group's members joining by password (applied by the next
    apply; people already connected stay until they re-authenticate)."""
    with vars_lock():
        data = load_vars()
        people = data.get("radius_people") or []
        kept = [m for m in people if str(m.get("group", "")).lower() != str(group).strip().lower()]
        if len(kept) == len(people):
            raise ValidationError(f"group {group} is not mapped for 802.1X")
        data["radius_people"] = kept
        save_vars(data)
    write_audit(actor, "RADIUS_GROUP_UNMAP", f"group={group}", source)
