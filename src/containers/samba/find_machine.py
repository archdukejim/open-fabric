import ldb

from paths import site_dn


def find_machine(samdb, site, name):
    """Purpose: a machine of the site by its name.
    Inputs:  samdb — SamDB; site — str; name — the host name (any case).
    Returns: ldb.Message (dn, userAccountControl).
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT when the site has no such machine.
    Feeds:   set_machine, remove_machine."""
    found = samdb.search(base=f"OU=machines,{site_dn(samdb, site)}", scope=ldb.SCOPE_SUBTREE,
                         expression=f"(&(objectCategory=computer)(sAMAccountName={ldb.binary_encode(name)}$))",
                         attrs=["userAccountControl"])
    if not found:
        raise ldb.LdbError(ldb.ERR_NO_SUCH_OBJECT, f"no machine {name} in site {site}")
    return found[0]
