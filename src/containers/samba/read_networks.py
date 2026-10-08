import ldb

from paths import sites_dn


def read_networks(samdb, lp, site):
    """Purpose: the address plan across sites (manual 2.2.2.8, S4.2): every site's networks, in one search over
             OU=sites — every DC holds the whole domain, so nothing is gathered.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str (unused: the plan is every
             site's).
    Returns: list of {"site", "name", "cidr", "vlan" (int or None), "kind", "notes", "allow_overlap"}, sorted by site
             and network.
    Fails:   ldb.LdbError from the search.
    Feeds:   directory_ops (op "read_networks")."""
    out = []
    for m in samdb.search(base=sites_dn(samdb), scope=ldb.SCOPE_SUBTREE, expression="(objectClass=fabricNetwork)",
                          attrs=["cn", "fabricSite", "fabricCidr", "fabricVlan", "fabricNetworkKind", "description",
                                 "fabricAllowOverlap"]):
        one = lambda name: str(m.get(name, idx=0) or "")    # noqa: E731
        out.append({"site": one("fabricSite"), "name": one("cn"), "cidr": one("fabricCidr"),
                    "vlan": int(one("fabricVlan")) if one("fabricVlan") else None,
                    "kind": one("fabricNetworkKind"), "notes": one("description"),
                    "allow_overlap": one("fabricAllowOverlap")})
    return sorted(out, key=lambda n: (n["site"], n["cidr"]))
