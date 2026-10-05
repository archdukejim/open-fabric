import ldb


def reset_password(samdb, lp, site, uid, password):
    """Purpose: a person's sign-in reset in the directory (manual 1.6.3.8): a new one-time password they must change
             at their next sign-in, and their account unlocked.
    Inputs:  samdb — SamDB (as the site's agent: AD refuses a person of another site); lp — LoadParm (unused);
             site — str (unused); uid — the user name; password — the one-time password (satisfies the policy).
    Returns: {"uid"}.
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT for no such person; ERR_INSUFFICIENT_ACCESS_RIGHTS outside the agent's
             site; ERR_CONSTRAINT_VIOLATION when the policy refuses the password.
    Feeds:   directory_ops (op "reset_password")."""
    found = samdb.search(base=f"OU=sites,{samdb.domain_dn()}", scope=ldb.SCOPE_SUBTREE,
                         expression=f"(&(objectCategory=person)(sAMAccountName={ldb.binary_encode(uid)}))",
                         attrs=["lockoutTime"])
    if not found or ",OU=service-accounts," in str(found[0].dn):
        raise ldb.LdbError(ldb.ERR_NO_SUCH_OBJECT, f"no user {uid}")
    samdb.setpassword(f"(sAMAccountName={ldb.binary_encode(uid)})", password, force_change_at_next_login=True)
    if int(str(found[0].get("lockoutTime", ["0"])[0])):
        samdb.modify(ldb.Message.from_dict(samdb, {"dn": str(found[0].dn), "lockoutTime": "0"}, ldb.FLAG_MOD_REPLACE))
    return {"uid": uid}
