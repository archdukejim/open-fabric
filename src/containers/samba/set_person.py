import ldb

from find_person import find_person

ACCOUNTDISABLE = 0x2


def set_person(samdb, lp, site, uid, enabled):
    """Purpose: disable a person of the site, or enable them again (manual 1.6.3.16): while disabled every sign-in
             through the domain is refused (Keycloak, 802.1X, Windows and Linux logons); the account and its groups
             stay.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str; uid — the user name; enabled —
             bool.
    Returns: {"uid", "enabled", "changed" (bool)}.
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT (not a person of this site), ERR_INSUFFICIENT_ACCESS_RIGHTS.
    Feeds:   directory_ops (op "set_person")."""
    p = find_person(samdb, site, uid)
    uac = int(str(p.get("userAccountControl", idx=0) or 0))
    want = uac & ~ACCOUNTDISABLE if enabled else uac | ACCOUNTDISABLE
    if want != uac:
        msg = ldb.Message(p.dn)
        msg["userAccountControl"] = ldb.MessageElement([str(want)], ldb.FLAG_MOD_REPLACE, "userAccountControl")
        samdb.modify(msg)
    return {"uid": uid, "enabled": bool(enabled), "changed": want != uac}
