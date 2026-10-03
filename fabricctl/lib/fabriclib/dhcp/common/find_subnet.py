from fabriclib.common.errors import ValidationError


def find_subnet(dhcp, which):
    """Purpose: the subnet a command names, by its name or its network.
    Inputs:  dhcp — the normalized dhcp block; which — a subnet name ("iot") or network ("192.168.20.0/24").
    Returns: the subnet dict (the object inside dhcp, so changes to it are saved).
    Fails:   ValidationError "no DHCP subnet …".
    Feeds:   dhcp/update_subnet, remove_subnet, set_option, unset_option."""
    key = str(which).strip().lower()
    for s in dhcp.get("subnets") or []:
        if key in (s.get("name"), s["subnet"]):
            return s
    raise ValidationError(f"no DHCP subnet {which!r} (a subnet's name or network)")
