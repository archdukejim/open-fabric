import ipaddress

from fabriclib.common.errors import ValidationError


def place_subnets(dhcp, host_ip, networks):
    """Purpose: each DHCP subnet placed on the host (manual 1.10.3.2): on the served interface whose network holds it,
             or behind a DHCP relay; fabric's address there is what its clients are told to use (2.1.10.5).
    Inputs:  dhcp — normalized `dhcp` (interfaces, subnets with optional relay); host_ip — this host's LAN address
             (a relayed subnet's server); networks — host_networks() ({interface: [IPv4Interface]}), or None when
             not on the fabric host (tests that only render): then no interface is checked and every subnet is
             served from host_ip.
    Returns: a copy of dhcp whose subnets each carry `server` (fabric's address for them) and `interface` (the one
             they are served on; absent when relayed or unchecked).
    Fails:   ValidationError: an interface in dhcp.interfaces this host does not have, or one with no IPv4 address;
             a subnet neither on a served interface nor relayed.
    Feeds:   deploy/check_settings; tests/kea/run.py."""
    out = {**dhcp, "subnets": [dict(s) for s in dhcp.get("subnets") or []]}
    if networks is None:
        for s in out["subnets"]:
            s["server"] = host_ip
        return out
    served = {}
    for iface in dhcp.get("interfaces") or []:
        if iface not in networks:
            raise ValidationError(f"dhcp.interfaces: this host has no interface {iface!r} (it has "
                                  f"{', '.join(sorted(networks)) or 'none with IPv4'})")
        served[iface] = networks[iface]
    for s in out["subnets"]:
        net = ipaddress.ip_network(s["subnet"])
        on = next(((i, a) for i, addrs in served.items() for a in addrs if a.network.overlaps(net)), None)
        if on:
            s["interface"], s["server"] = on[0], str(on[1].ip)
        elif s.get("relay"):
            s["server"] = host_ip
        else:
            raise ValidationError(f"{net}: not on a served interface ({', '.join(served)}) and no relay set: serve "
                                  "the interface it is on, or set the subnet's relay (the DHCP relay's address)")
    return out
