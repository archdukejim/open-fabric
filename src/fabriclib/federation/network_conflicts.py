import ipaddress


def network_conflicts(mine, plan, site):
    """Purpose: which of this site's networks overlap another site's (manual 1.10.2.6): two sites
             routed together must never share addresses.
    Inputs:  mine — this site's networks (site_networks); plan — the address plan (read_address_plan: entries
             with "site", "name", "cidr", "allow_overlap"); site — this site's name (its own entries are skipped).
    Returns: list of {"name", "cidr", "other_site", "other_name", "other_cidr", "allowed" (the reason when either
             side gave one with allow_overlap, else "")}, sorted by this site's network.
    Fails:   ValueError for a network that is not one (the plan is written by fabric, so only on corruption).
    Feeds:   dhcp/common/edit_dhcp (refuses unallowed ones), accept_join (refuses at join),
             federation/run_federation_command (`networks`: shown as conflicts)."""
    out = []
    for m in mine:
        net = ipaddress.ip_network(m["cidr"], strict=False)
        for p in plan:
            if p.get("site") == site:
                continue
            other = ipaddress.ip_network(p["cidr"], strict=False)
            if net.overlaps(other):
                out.append({"name": m["name"], "cidr": m["cidr"], "other_site": p["site"],
                            "other_name": p.get("name", ""), "other_cidr": p["cidr"],
                            "allowed": m.get("allow_overlap") or p.get("allow_overlap") or ""})
    return sorted(out, key=lambda c: (c["cidr"], c["other_site"]))
