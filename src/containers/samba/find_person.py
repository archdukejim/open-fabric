import ldb

from paths import site_dn


def find_person(samdb, site, uid):
    """Purpose: a person of the site by user name: only the site's own people (its OU=people), never a service
             account or another site's person (manual 1.6.3.16).
    Inputs:  samdb — SamDB; site — str; uid — the user name.
    Returns: ldb.Message (dn, userAccountControl, memberOf).
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT when the site has no such person.
    Feeds:   set_person, remove_person."""
    found = samdb.search(base=f"OU=people,{site_dn(samdb, site)}", scope=ldb.SCOPE_ONELEVEL,
                         expression=f"(&(objectCategory=person)(objectClass=user)"
                                    f"(sAMAccountName={ldb.binary_encode(uid)}))",
                         attrs=["userAccountControl", "memberOf"])
    if not found:
        raise ldb.LdbError(ldb.ERR_NO_SUCH_OBJECT, f"no person {uid} in site {site}")
    return found[0]
