def client_networks(v):
    """Purpose: the networks of DHCP's clients and fabric's addresses facing them, split by what they may reach
             (2.1.10.4, manual 1.10.3.3): full subnets get fabric's services like the host's LAN, guest subnets
             DNS through the filter and NTP only.
    Inputs:  v — rendered vars: install_kea; dhcp.subnets [{subnet, access ("full" default, or "guest"), server
             (fabric's address for them, set by place_subnets)}].
    Returns: {"full": [subnet, ...], "guest": [subnet, ...], "full_addrs": [address, ...], "guest_addrs":
             [address, ...]}: each list deduplicated, in subnet order; all empty when DHCP is off.
    Fails:   never.
    Feeds:   dns/builtin_acls, dns_filter (the resolver's clients, check_filter_groups), security/firewall_rules,
             security/apply_docker_firewall, deploy/check_settings (dhcp_served for the templates)."""
    out = {"full": [], "guest": [], "full_addrs": [], "guest_addrs": []}
    if not v.get("install_kea"):
        return out
    for s in (v.get("dhcp") or {}).get("subnets") or []:
        kind = "guest" if s.get("access") == "guest" else "full"
        for key, value in ((kind, s.get("subnet")), (f"{kind}_addrs", s.get("server"))):
            if value and value not in out[key]:
                out[key].append(value)
    return out
