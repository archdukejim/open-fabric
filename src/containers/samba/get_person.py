import ldb


def get_person(samdb, lp, site, uid):
    """Purpose: one person by user name, anywhere in the domain: where they live and the groups they are in (what a
             reset's guard needs, manual 1.6.3.8).
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str (unused); uid — the user name.
    Returns: {"uid", "dn", "groups" [names]}.
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT when there is no such person (service accounts are not people).
    Feeds:   directory_ops (op "get_person")."""
    found = samdb.search(base=f"OU=sites,{samdb.domain_dn()}", scope=ldb.SCOPE_SUBTREE,
                         expression=f"(&(objectCategory=person)(objectClass=user)"
                                    f"(sAMAccountName={ldb.binary_encode(uid)}))", attrs=["memberOf"])
    if not found or ",OU=service-accounts," in str(found[0].dn):
        raise ldb.LdbError(ldb.ERR_NO_SUCH_OBJECT, f"no user {uid}")
    return {"uid": uid, "dn": str(found[0].dn),
            "groups": sorted(str(g).split(",", 1)[0].split("=", 1)[1] for g in found[0].get("memberOf", []))}
