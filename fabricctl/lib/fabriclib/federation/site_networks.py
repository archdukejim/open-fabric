import ipaddress


def site_networks(v):
    """Purpose: the networks this site uses, as the address plan across sites records them (design
             dhcp-management.md §5): its LAN and every DHCP subnet, with name, VLAN, notes and an overlap reason.
    Inputs:  v — fabric vars: lan_cidr; install_kea and dhcp.subnets [{subnet, name, vlan, notes, allow_overlap}].
    Returns: list of {"name", "cidr", "kind" ("lan" | "dhcp"), "vlan" (int or None), "notes", "allow_overlap"}, one
             per distinct network (a DHCP subnet that is the LAN itself is listed once, as the DHCP subnet with
             its name); names are unique (a subnet without a name is named by its network).
    Fails:   never for missing settings (an empty list); ValueError for a lan_cidr that is not a network.
    Feeds:   federation/publish_site_networks, federation/join_upstream (sent at join), accept_join and
             dhcp/common/edit_dhcp (overlap checks)."""
    out, seen = [], set()
    if v.get("install_kea"):
        for s in (v.get("dhcp") or {}).get("subnets") or []:
            cidr = str(ipaddress.ip_network(str(s["subnet"]), strict=False))
            if cidr in seen:
                continue
            seen.add(cidr)
            out.append({"name": s.get("name") or cidr, "cidr": cidr, "kind": "dhcp", "vlan": s.get("vlan"),
                        "notes": s.get("notes") or "", "allow_overlap": s.get("allow_overlap") or ""})
    if v.get("lan_cidr"):
        cidr = str(ipaddress.ip_network(str(v["lan_cidr"]), strict=False))
        if cidr not in seen:
            out.insert(0, {"name": "lan", "cidr": cidr, "kind": "lan", "vlan": None, "notes": "", "allow_overlap": ""})
    return out
