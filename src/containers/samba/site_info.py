import ldb


def site_info(samdb, lp, site):
    """Purpose: what the directory knows of a site: its OU, its id block and how far it is used.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused: every operation takes it); site — str.
    Returns: dict {"dn", "id_range" "first-last", "id_next" int}.
    Fails:   ldb.LdbError (no such OU, or not readable).
    Feeds:   directory_ops (op "site_info")."""
    dn = f"OU={site},OU=sites,{samdb.domain_dn()}"
    res = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=["fabricIdRange", "fabricIdNext"])[0]
    return {"dn": dn, "id_range": str(res["fabricIdRange"][0]), "id_next": int(str(res["fabricIdNext"][0]))}
