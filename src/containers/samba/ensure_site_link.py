import ldb

COST = "100"
INTERVAL = "15"                  # minutes; changes are also notified at once (options: USE_NOTIFY)
USE_NOTIFY = "1"


def ensure_site_link(samdb, site, parent):
    """Purpose: the AD site link between a site and its parent (manual 1.8.8.5, S8.3): cost 100, every 15 minutes and
             on change notification, so AD's KCC builds replication both ways between their DCs.
    Inputs:  samdb — SamDB (as the system); site — the site; parent — its parent site.
    Returns: list of str, what changed.
    Fails:   ldb.LdbError for a change AD refuses (e.g. either AD site missing: ensure_ad_site makes them).
    Feeds:   converge (state parent)."""
    sites = f"CN=Sites,{samdb.get_config_basedn()}"
    dn = f"CN={parent}-{site},CN=IP,CN=Inter-Site Transports,{sites}"
    want = {"siteList": sorted([f"CN={parent},{sites}", f"CN={site},{sites}"]), "cost": [COST],
            "replInterval": [INTERVAL], "options": [USE_NOTIFY]}
    try:
        found = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=list(want))
    except ldb.LdbError as e:
        if e.args[0] != ldb.ERR_NO_SUCH_OBJECT:
            raise
        found = []
    if not found:
        samdb.add({"dn": dn, "objectClass": "siteLink", **want})
        return [f"site link {parent}-{site} created"]
    msg = ldb.Message(found[0].dn)
    for attr, val in want.items():
        if sorted(str(x).lower() for x in found[0].get(attr, [])) != sorted(x.lower() for x in val):
            msg[attr] = ldb.MessageElement(val, ldb.FLAG_MOD_REPLACE, attr)
    if len(msg) == 0:
        return []
    samdb.modify(msg)
    return [f"site link {parent}-{site} changed"]
