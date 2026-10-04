import ldb


def _ensure_group(samdb, name, ou):
    """Purpose: a global security group, created when missing.
    Inputs:  samdb — SamDB; name — sAMAccountName; ou — str, the OU relative to the domain ("OU=groups,OU=lan,...").
    Returns: True if it was created.
    Fails:   ldb.LdbError from the creation, or when the name exists elsewhere in the domain (names are unique).
    Feeds:   ensure_groups."""
    if samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                    expression=f"(sAMAccountName={ldb.binary_encode(name)})", attrs=["dn"]):
        return False
    samdb.newgroup(name, groupou=ou)
    return True


def ensure_groups(samdb, site, root):
    """Purpose: the groups access is built on (manual 1.6.3.6, 1.6.3.10): the site's people and admins, and, at the
             root site, the organisation's admins and its break-glass group (in every site's log-on policy, so a
             mistake cannot lock everyone out).
    Inputs:  samdb — SamDB; site — str; root — bool.
    Returns: list of str, the groups created.
    Fails:   ldb.LdbError from a creation.
    Feeds:   converge."""
    site_groups = f"OU=groups,OU={site},OU=sites"
    wanted = [(f"{site}-users", site_groups), (f"{site}-admins", site_groups)]
    if root:
        org = f"OU=groups,OU=organisation,OU={site},OU=sites"
        wanted += [("fabric-admins", org), ("fabric-break-glass", org)]
    return [name for name, ou in wanted if _ensure_group(samdb, name, ou)]
