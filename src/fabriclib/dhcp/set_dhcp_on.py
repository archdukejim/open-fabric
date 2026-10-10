import copy

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp
from fabriclib.dhcp.place_subnets import place_subnets
from fabriclib.system.host_networks import host_networks


def set_dhcp_on(actor, on, interface="", subnet="", pool="", router="", source="cli", networks=None):
    """Purpose: turn DHCP on or off (manual 1.10.3.5). On: with its settings kept from before, as they were; with none,
             a first subnet on the interface given. Off: Kea stops at the next apply and what it added goes (the DNS
             key and zones, its subnets' access); its settings and leases are kept, so on resumes.
    Inputs:  actor — who asks (audit); on — bool; interface, subnet (a network), pool ("a - b"), router (optional) —
             the first subnet when DHCP has none yet; source — "cli" or "web"; networks — host_networks() (None: read
             this host's), where the subnet must lie.
    Returns: {"on": bool, "interfaces": [...], "subnets": [network, ...]} as saved.
    Fails:   ValidationError: already in that state; on with no settings and no interface, subnet or pool given; what
             normalize_dhcp or place_subnets refuses (an interface the host lacks, a subnet not on it, a bad pool).
             Nothing is saved then. OSError or yaml.YAMLError from the lock, the settings or the audit log.
    Feeds:   dhcp/run_dhcp_command (`fabricctl dhcp on|off`), agent/post_dhcp (POST /v1/dhcp/on, /v1/dhcp/off)."""
    with vars_lock():
        data = load_vars()
        if bool(data.get("install_kea")) == on:
            raise ValidationError(f"DHCP is already {'on' if on else 'off'}")
        dhcp = copy.deepcopy(data.get("dhcp") or {})
        if on:
            if not dhcp.get("subnets"):
                if not (interface and subnet and pool):
                    raise ValidationError("DHCP has no settings yet: give the interface, the subnet and a pool")
                dhcp = {**dhcp, "interfaces": [interface],
                        "subnets": [{"subnet": subnet, "pools": [pool], **({"routers": router} if router else {})}]}
            dhcp = normalize_dhcp({**data, "dhcp": dhcp, "install_kea": True})
            place_subnets(dhcp, data.get("host_ip"), networks if networks is not None else host_networks())
            data["dhcp"] = dhcp
        data["install_kea"] = on
        save_vars(data)
    nets = [s["subnet"] for s in (data.get("dhcp") or {}).get("subnets") or []]
    write_audit(actor, "DHCP_ON" if on else "DHCP_OFF",
                f"interfaces {', '.join((data.get('dhcp') or {}).get('interfaces') or [])}; subnets {', '.join(nets)}",
                source)
    return {"on": on, "interfaces": list((data.get("dhcp") or {}).get("interfaces") or []), "subnets": nets}
