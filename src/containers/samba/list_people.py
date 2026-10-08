import ldb

UF_ACCOUNTDISABLE = 0x2


def _cn(dn):
    """Purpose: the first RDN's value of a DN ("CN=admins,OU=…" -> "admins").
    Inputs:  dn — str.
    Returns: str.
    Fails:   never.
    Feeds:   list_people."""
    return dn.split(",", 1)[0].split("=", 1)[1]


def _site(dn):
    """Purpose: the site a person or group lives in: the OU enclosing its container (OU=people, OU=groups), since
             sites nest (2.1.6.20); "organisation" for the organisation's groups.
    Inputs:  dn — str.
    Returns: str, or "" outside OU=sites.
    Fails:   never.
    Feeds:   list_people."""
    parts = dn.split(",")
    if not any(p.upper() == "OU=SITES" for p in parts) or len(parts) < 3:
        return ""
    return parts[2].split("=", 1)[1]


def list_people(samdb, lp, site):
    """Purpose: the People page (manual 1.6.3): every person under OU=sites (service accounts left out) and the
             groups they may be in, never a password or a hash.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str (unused: people are listed
             across the domain, 2.1.6.14; who may change whom is AD's access control).
    Returns: {"users": [{uid, name, mail, locked (disabled or locked out), groups [names], site, uidNumber}],
              "groups": [{name, members (count)}]}, both sorted by name.
    Fails:   ldb.LdbError from a search.
    Feeds:   directory_ops (op "list_people")."""
    base = f"OU=sites,{samdb.domain_dn()}"
    users = []
    for m in samdb.search(base=base, scope=ldb.SCOPE_SUBTREE,
                          expression="(&(objectCategory=person)(objectClass=user)(!(objectClass=computer)))",
                          attrs=["sAMAccountName", "displayName", "mail", "memberOf", "userAccountControl",
                                 "lockoutTime", "uidNumber"]):
        dn = str(m.dn)
        if ",OU=service-accounts," in dn:
            continue
        uac = int(str(m.get("userAccountControl", ["0"])[0]))
        locked = bool(uac & UF_ACCOUNTDISABLE) or int(str(m.get("lockoutTime", ["0"])[0])) > 0
        users.append({"uid": str(m["sAMAccountName"][0]), "name": str(m.get("displayName", [""])[0]),
                      "mail": str(m.get("mail", [""])[0]), "locked": locked,
                      "groups": sorted(_cn(str(g)) for g in m.get("memberOf", [])), "site": _site(dn),
                      "uidNumber": int(str(m["uidNumber"][0])) if "uidNumber" in m else None})
    groups = [{"name": str(g["cn"][0]), "members": len(g.get("member", []))}
              for g in samdb.search(base=base, scope=ldb.SCOPE_SUBTREE, expression="(objectClass=group)",
                                    attrs=["cn", "member"])]
    return {"users": sorted(users, key=lambda u: u["uid"]), "groups": sorted(groups, key=lambda g: g["name"])}
