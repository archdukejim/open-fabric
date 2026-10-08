import ldb
from samba import sites, subnets

# subnets fabric made carry this description; others (an admin's own) are never touched
MARK = "fabric: address plan"


def ensure_ad_site(samdb, site, networks):
    """Purpose: the AD site of this fabric site and its subnets from the address plan (manual 1.9.8.5, 1.10.2.8), so
             Windows machines find their own site's DC by their subnet.
    Inputs:  samdb — SamDB; site — str; networks — list of CIDR str (the site's LAN and DHCP subnets).
    Returns: list of str, what was created, moved or removed.
    Fails:   ldb.LdbError or the samba.sites / samba.subnets exceptions for a change AD refuses.
    Feeds:   converge.
    Notes:   a new domain's DC sits in AD's Default-First-Site-Name: that site is renamed to the fabric site (the DC
             moves with it). A subnet fabric made that left the plan is removed."""
    config = str(samdb.get_config_basedn())
    sites_dn = f"CN=Sites,{config}"
    done = []
    names = {str(m["cn"]) for m in samdb.search(base=sites_dn, scope=ldb.SCOPE_ONELEVEL,
                                                expression="(objectClass=site)", attrs=["cn"])}
    if site not in names:
        if "Default-First-Site-Name" in names:
            samdb.rename(f"CN=Default-First-Site-Name,{sites_dn}", f"CN={site},{sites_dn}")
            done.append(f"AD site Default-First-Site-Name renamed {site}")
        else:
            sites.create_site(samdb, config, site)
            done.append(f"AD site {site} created")
    subnets_dn = f"CN=Subnets,{sites_dn}"
    have = {str(m["cn"]): m for m in samdb.search(base=subnets_dn, scope=ldb.SCOPE_ONELEVEL,
                                                    expression="(objectClass=subnet)",
                                                    attrs=["cn", "siteObject", "description"])}
    site_dn = f"CN={site},{sites_dn}"
    for cidr in networks:
        if cidr not in have:
            subnets.create_subnet(samdb, config, cidr, site)
            samdb.modify(ldb.Message.from_dict(samdb, {"dn": f"CN={cidr},{subnets_dn}", "description": MARK},
                                               ldb.FLAG_MOD_REPLACE))
            done.append(f"subnet {cidr} -> {site}")
        elif str(have[cidr].get("siteObject", [""])[0]).lower() != site_dn.lower():
            subnets.set_subnet_site(samdb, config, cidr, site)
            done.append(f"subnet {cidr} moved to {site}")
    for cidr, m in have.items():
        if cidr not in networks and str(m.get("description", [""])[0]) == MARK \
                and str(m.get("siteObject", [""])[0]).lower() == site_dn.lower():
            subnets.delete_subnet(samdb, config, cidr)
            done.append(f"subnet {cidr} removed (no longer in the plan)")
    return done
