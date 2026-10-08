from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.common.find_subnet import find_subnet


def option_target(dhcp, subnet=None, client_class=None, mac=None):
    """Purpose: the place an option command works on: every subnet (global), one subnet, one client class, or one
             reservation (manual 1.10.2.3: Kea's levels, most specific wins).
    Inputs:  dhcp — the normalized dhcp block; subnet — a subnet's name or network; client_class — a class name;
             mac — a reservation's MAC. At most one of the three.
    Returns: (the dict whose "options" list to change, a label for messages and the audit).
    Fails:   ValidationError: more than one place given; no such subnet, class or reservation.
    Feeds:   dhcp/set_option, dhcp/unset_option."""
    given = [x for x in (subnet, client_class, mac) if x]
    if len(given) > 1:
        raise ValidationError("an option goes to one place: --subnet, --class or --mac (none: every subnet)")
    if subnet:
        s = find_subnet(dhcp, subnet)
        return s, f"subnet {s.get('name', s['subnet'])}"
    if client_class:
        for c in dhcp.get("client_classes") or []:
            if c["name"] == client_class:
                return c, f"class {client_class}"
        raise ValidationError(f"no client class {client_class!r}")
    if mac:
        m = str(mac).strip().lower().replace("-", ":")
        for s in dhcp.get("subnets") or []:
            for r in s.get("reservations") or []:
                if r["mac"] == m:
                    return r, f"reservation {m}"
        raise ValidationError(f"no reservation for {m}")
    return dhcp, "every subnet"
