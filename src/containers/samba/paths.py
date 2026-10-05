def site_dn(samdb, site):
    """Purpose: a site's OU.
    Inputs:  samdb — SamDB; site — str.
    Returns: str "OU=<site>,OU=sites,<domain>".
    Fails:   never.
    Feeds:   the directory operations."""
    return f"OU={site},OU=sites,{samdb.domain_dn()}"


def devices_dn(samdb, site):
    """Purpose: a site's devices (manual 1.6.3.4).
    Inputs:  samdb — SamDB; site — str.
    Returns: str.
    Fails:   never.
    Feeds:   the device operations."""
    return f"OU=devices,{site_dn(samdb, site)}"


def sites_dn(samdb):
    """Purpose: everything fabric manages (D88).
    Inputs:  samdb — SamDB.
    Returns: str "OU=sites,<domain>".
    Fails:   never.
    Feeds:   the directory operations (searches across sites)."""
    return f"OU=sites,{samdb.domain_dn()}"
