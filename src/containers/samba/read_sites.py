"""Every site the domain holds (manual 1.6.3.4, 1.6.3.9): each site OU's name, where it sits and its uid/gid block,
read from this DC's own database, so a parent that is not the root hands a new site a block no other site has, and
sees a site that moves under it (D105) already exists.
    docker exec samba python3 /fabric/read_sites.py
Prints one JSON object: {"sites": [{"site", "dn", "id_range"}, …]}."""
import json
import sys

import ldb

from open_samdb import open_samdb

CONF = "/data/etc/smb.conf"


def read_sites():
    """Purpose: the sites in the domain.
    Inputs:  none (the DC's own database, as the system).
    Returns: {"sites": [{"site", "dn", "id_range" ("first-last", or "" before its block is set)}]}, by name.
    Fails:   ldb.LdbError from the search.
    Feeds:   this script's main."""
    samdb, _ = open_samdb(CONF)
    res = samdb.search(base=f"OU=sites,{samdb.domain_dn()}", scope=ldb.SCOPE_SUBTREE,
                       expression="(objectClass=fabricSiteInfo)", attrs=["ou", "fabricIdRange"])
    return {"sites": sorted(({"site": str(r["ou"][0]), "dn": str(r.dn),
                              "id_range": str(r.get("fabricIdRange", [""])[0])} for r in res),
                            key=lambda s: s["site"])}


if __name__ == "__main__":
    try:
        print(json.dumps(read_sites()))
    except Exception as e:                  # reported by the caller; the DC keeps running
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
