import re

from fabriclib.common.errors import ValidationError

GROUP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._-]{0,63}$")


def normalize_radius_people(mappings):
    """Check `radius_people`: which directory groups may join the network
    by password (EAP-TTLS), each with an optional VLAN (1-4094) and a
    priority (lower wins when a person is in several). Returns the list,
    sorted by priority then group."""
    out, seen = [], set()
    for m in mappings or []:
        if not isinstance(m, dict):
            raise ValidationError("radius_people: each entry is {group, vlan, priority}")
        group = str(m.get("group", "")).strip()
        if not GROUP_RE.match(group):
            raise ValidationError(f"radius_people: {group!r} is not a group name")
        if group.lower() in seen:
            raise ValidationError(f"radius_people: {group} is mapped twice")
        vlan = m.get("vlan")
        if vlan in (None, "", 0, "0"):
            vlan = None
        else:
            try:
                vlan = int(vlan)
            except (TypeError, ValueError):
                vlan = -1
            if not 1 <= vlan <= 4094:
                raise ValidationError(f"radius_people: {group}: VLAN must be 1-4094")
        try:
            priority = int(m.get("priority", 100) if m.get("priority") not in (None, "") else 100)
        except (TypeError, ValueError):
            priority = -1
        if not 0 <= priority <= 9999:
            raise ValidationError(f"radius_people: {group}: priority must be 0-9999")
        seen.add(group.lower())
        out.append({"group": group, "vlan": vlan, "priority": priority})
    return sorted(out, key=lambda m: (m["priority"], m["group"].lower()))
