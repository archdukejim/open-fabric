import ldb

from alloc_id import alloc_id


def create_person(samdb, lp, site, uid, first, last, email, password, gid, home_base, shell):
    """Purpose: a new person in a site (manual 1.6.3.4, 1.6.3.9, 1.6.3.10): a user in the site's OU=people named by
             its user name, with their POSIX identity (a uid from the site's block, never reused), a member of
             `<site>-users`, and a one-time password they must change at their first sign-in.
    Inputs:  samdb — SamDB (as the site's agent: AD refuses another site); lp — LoadParm (unused); site — str;
             uid — the user name (checked by the caller); first, last, email — str; password — the one-time
             password (it must satisfy the domain's policy); gid — int, their primary gid (fabric's users: 5000);
             home_base — str (e.g. /home); shell — str (e.g. /bin/bash).
    Returns: {"uid", "uidNumber"}.
    Fails:   ldb.LdbError ERR_ENTRY_ALREADY_EXISTS when the user name or the e-mail address is taken anywhere in the
             domain; ERR_CONSTRAINT_VIOLATION when the policy refuses the password; ERR_INSUFFICIENT_ACCESS_RIGHTS
             outside the agent's site; ValueError when the site's id block is full.
    Feeds:   directory_ops (op "create_person")."""
    base = str(samdb.domain_dn())
    taken = samdb.search(base=base, scope=ldb.SCOPE_SUBTREE,
                         expression=f"(|(sAMAccountName={ldb.binary_encode(uid)})(mail={ldb.binary_encode(email)}))",
                         attrs=["dn"])
    if taken:
        raise ldb.LdbError(ldb.ERR_ENTRY_ALREADY_EXISTS, f"{uid} (or that e-mail address) already exists")
    number = alloc_id(samdb, f"OU={site},OU=sites,{base}")
    samdb.newuser(uid, password, force_password_change_at_next_login_req=True, useusernameascn=True,
                  userou=f"OU=people,OU={site},OU=sites", givenname=first, surname=last, mailaddress=email,
                  uidnumber=number, gidnumber=gid, loginshell=shell, unixhome=f"{home_base}/{uid}", uid=uid)
    samdb.add_remove_group_members(f"{site}-users", [uid], add_members_operation=True)
    return {"uid": uid, "uidNumber": number}
