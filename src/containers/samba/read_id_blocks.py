"""Every site's uid/gid block as the domain records it (manual 1.6.3.9, D97): the `fabricIdRange` of each site OU,
read from this DC's own database, so a parent that is not the root hands a new site a block no other site has.
    docker exec samba python3 /fabric/read_id_blocks.py
Prints one JSON object: {"blocks": ["first-last", …]}."""
import json
import sys

import ldb

from open_samdb import open_samdb

CONF = "/data/etc/smb.conf"


def read_id_blocks():
    """Purpose: the id blocks of every site in the domain.
    Inputs:  none (the DC's own database, as the system).
    Returns: {"blocks": [str "first-last"]}.
    Fails:   ldb.LdbError from the search.
    Feeds:   this script's main."""
    samdb, _ = open_samdb(CONF)
    res = samdb.search(base=f"OU=sites,{samdb.domain_dn()}", scope=ldb.SCOPE_SUBTREE,
                       expression="(&(objectClass=fabricSiteInfo)(fabricIdRange=*))", attrs=["fabricIdRange"])
    return {"blocks": sorted(str(r["fabricIdRange"][0]) for r in res)}


if __name__ == "__main__":
    try:
        print(json.dumps(read_id_blocks()))
    except Exception as e:                  # reported by the caller; the DC keeps running
        print(f"{type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
