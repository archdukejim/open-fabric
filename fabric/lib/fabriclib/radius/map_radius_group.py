from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.radius.normalize_radius_people import normalize_radius_people


def map_radius_group(actor, group, vlan=None, priority=100, source="cli"):
    """Let the members of a directory group join the network by password
    (EAP-TTLS), optionally on a VLAN; replaces that group's mapping if it
    has one. Applied by the next apply. Returns the mapping."""
    with vars_lock():
        data = load_vars()
        if not data.get("install_freeradius"):
            raise ValidationError("802.1X is off (install_freeradius: false)")
        others = [m for m in data.get("radius_people") or [] if str(m.get("group", "")).lower() != str(group).lower()]
        people = normalize_radius_people(others + [{"group": group, "vlan": vlan, "priority": priority}])
        data["radius_people"] = people
        save_vars(data)
    saved = next(m for m in people if m["group"].lower() == str(group).strip().lower())
    write_audit(actor, "RADIUS_GROUP_MAP", f"group={saved['group']} vlan={saved['vlan'] or '-'} "
                                           f"priority={saved['priority']}", source)
    return saved
