import ipaddress

from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.common.edit_dhcp import edit_dhcp
from fabriclib.dhcp.common.find_subnet import find_subnet


def remove_subnet(actor, which, leases, force=False, source="cli"):
    """Purpose: remove a DHCP subnet, its pools and reservations (manual 2.2.2.4-4). The other
             subnets keep their ids, so their leases stay theirs. Applied by the next apply.
    Inputs:  actor — who asks (audit); which — the subnet's name or network; leases — the leases Kea holds now
             (list_leases; [] when Kea is off; None when they could not be read — then only with force);
             force — remove even with active leases in it; source.
    Returns: the removed subnet's network (str).
    Fails:   ValidationError: no such subnet; active leases in it, or leases unknown, without force (says how
             many); the last subnet (normalize_dhcp: DHCP needs one — turn DHCP off instead); OSError /
             yaml.YAMLError.
    Feeds:   run_dhcp_command (remove-subnet), agent route POST /v1/dhcp/subnets/<subnet>/delete."""
    def change(dhcp):
        s = find_subnet(dhcp, which)
        net = ipaddress.ip_network(s["subnet"])
        if leases is None and not force:
            raise ValidationError("Kea's leases cannot be read now, so active leases in "
                                  f"{s['subnet']} cannot be ruled out: remove it with --force")
        active = [l for l in leases or [] if ipaddress.ip_address(l["ip"]) in net and l.get("state") != "expired"]
        if active and not force:
            raise ValidationError(f"{s['subnet']} has {len(active)} active lease(s): clients would lose their "
                                  "addresses at renewal. Remove it anyway with --force")
        dhcp["subnets"] = [x for x in dhcp["subnets"] if x is not s]
        return s["subnet"], f"subnet={s['subnet']} name={s.get('name', '')} active_leases={len(active)}"
    return edit_dhcp(actor, "DHCP_SUBNET_REMOVE", change, source)[0]
