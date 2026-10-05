import time

import ldb

LIFETIME = 3600          # seconds: a join account is good for one hour (manual 1.8.8.4)


def _filetime(epoch):
    """Purpose: an AD timestamp (100 ns since 1601) for a time.
    Inputs:  epoch — seconds since 1970.
    Returns: str.
    Fails:   never.
    Feeds:   ensure_join_account."""
    return str(int((epoch + 11644473600) * 10_000_000))


def ensure_join_account(samdb, name, password):
    """Purpose: the temporary account a new site's DC joins the domain with (manual 1.8.8.4, S8.1): a member of
             Domain Admins (Samba's DC join needs it), expiring one hour from now; the site deletes it once joined.
             Made again (password and expiry renewed) if the join is retried.
    Inputs:  samdb — SamDB (as the system, at the root); name — sAMAccountName (fabric-join-<site>); password — str.
    Returns: list of str, what changed.
    Fails:   ldb.LdbError for a change AD refuses (e.g. a password the policy refuses).
    Feeds:   converge (state join_account)."""
    found = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                         expression=f"(&(objectClass=user)(sAMAccountName={ldb.binary_encode(name)}))", attrs=["dn"])
    if found:
        samdb.setpassword(f"(sAMAccountName={ldb.binary_encode(name)})", password, force_change_at_next_login=False)
        dn, done = found[0].dn, f"join account {name}: renewed"
    else:
        samdb.newuser(name, password, force_password_change_at_next_login_req=False)
        dn = samdb.search(base=str(samdb.domain_dn()), scope=ldb.SCOPE_SUBTREE,
                          expression=f"(sAMAccountName={ldb.binary_encode(name)})", attrs=["dn"])[0].dn
        samdb.add_remove_group_members("Domain Admins", [name], add_members_operation=True)
        done = f"join account {name}: created"
    msg = ldb.Message(dn)
    msg["accountExpires"] = ldb.MessageElement([_filetime(time.time() + LIFETIME)], ldb.FLAG_MOD_REPLACE,
                                               "accountExpires")
    samdb.modify(msg)
    return [done]
