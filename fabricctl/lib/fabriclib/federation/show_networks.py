from fabriclib.federation.network_conflicts import network_conflicts
from fabriclib.federation.read_address_plan import read_address_plan
from fabriclib.federation.site_networks import site_networks


def show_networks(v):
    """Purpose: print the address plan across sites for `fabricctl federation networks` (design
             dhcp-management.md §5): site → network → VLAN → kind → notes, then every overlap between sites
             (with the reason when one was given).
    Inputs:  v — fabric vars: ldap_base_dn, site_name, lan_cidr, dhcp (this site's networks are shown from its
             settings until the root's plan lists them).
    Returns: the number of overlaps without a reason (0: none).
    Fails:   ValidationError / RuntimeError from read_address_plan (389-DS not running).
    Feeds:   federation/run_federation_command (`networks`)."""
    plan = read_address_plan(v)
    site = v.get("site_name") or ""
    if not any(p["site"] == site for p in plan):
        plan += [{**n, "site": site, "unpublished": True} for n in site_networks(v)]
    if not plan:
        print("no networks yet")
        return 0
    print(f"{'site':<16} {'network':<20} {'name':<16} {'VLAN':<6} {'kind':<6} notes")
    for p in sorted(plan, key=lambda n: (n["site"], n["cidr"])):
        print(f"{p['site']:<16} {p['cidr']:<20} {p.get('name', ''):<16} {str(p.get('vlan') or '-'):<6} "
              f"{p.get('kind', ''):<6} {p.get('notes', '')}" + ("  (not in the root's plan yet)"
                                                                 if p.get("unpublished") else ""))
    seen, unallowed = set(), 0
    for s in sorted({p["site"] for p in plan}):
        for c in network_conflicts([p for p in plan if p["site"] == s], plan, s):
            pair = tuple(sorted([(s, c["cidr"]), (c["other_site"], c["other_cidr"])]))
            if pair in seen:
                continue
            seen.add(pair)
            unallowed += not c["allowed"]
            print(f"OVERLAP {s} {c['cidr']} and {c['other_site']} {c['other_cidr']}"
                  + (f" (allowed: {c['allowed']})" if c["allowed"] else ""))
    return unallowed
