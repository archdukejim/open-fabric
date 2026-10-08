from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.common.edit_dhcp import edit_dhcp
from fabriclib.dhcp.common.find_subnet import find_subnet

KEEP = object()     # "not given": leave the field as it is


def update_subnet(actor, which, name=KEEP, vlan=KEEP, router=KEEP, notes=KEEP, add_pools=(), remove_pools=(),
                  allow_overlap=KEEP, source="cli"):
    """Purpose: change a DHCP subnet's name, VLAN record, router, notes or pools (manual 1.10.2.5).
             Its network and id stay (leases are tied to the id). Applied by the next apply.
    Inputs:  actor — who asks (audit); which — the subnet's name or network; name, vlan, router, notes,
             allow_overlap (why it may overlap another site's network) — the new
             value, None or "" to clear it, KEEP (default) to leave it; add_pools / remove_pools — "first - last"
             strings; source — "cli" or "web".
    Returns: the saved subnet (normalized).
    Fails:   ValidationError: no such subnet; a pool to remove that is not there; anything normalize_dhcp refuses
             (name or vlan taken, pool overlapping, a reservation now inside a pool, …); OSError / yaml.YAMLError.
    Feeds:   run_dhcp_command (set-subnet), agent route POST /v1/dhcp/subnets/<subnet>."""
    def change(dhcp):
        s = find_subnet(dhcp, which)
        for key, value in (("name", name), ("vlan", vlan), ("routers", router), ("notes", notes),
                           ("allow_overlap", allow_overlap)):
            if value is KEEP:
                continue
            if value in (None, ""):
                s.pop(key, None)
            else:
                s[key] = value
        pools = [p.replace(" ", "") for p in s.get("pools") or []]
        for p in remove_pools:
            if p.replace(" ", "") not in pools:
                raise ValidationError(f"{s['subnet']} has no pool {p}")
        s["pools"] = [p for p in s.get("pools") or [] if p.replace(" ", "") not in
                      {r.replace(" ", "") for r in remove_pools}] + list(add_pools)
        return s["id"], f"subnet={s['subnet']} changed"
    sid, dhcp = edit_dhcp(actor, "DHCP_SUBNET_UPDATE", change, source)
    return next(s for s in dhcp["subnets"] if s["id"] == sid)
