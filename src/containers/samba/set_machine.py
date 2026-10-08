import ldb

from find_machine import find_machine

ACCOUNTDISABLE = 0x2


def set_machine(samdb, lp, site, name, enabled):
    """Purpose: disable a machine of the site, or enable it again (manual 1.6.7.6): a disabled machine's logons
             and its PEAP sign-in are refused, its account kept.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str; name — the host name; enabled —
             bool.
    Returns: {"name", "enabled", "changed" (bool)}.
    Fails:   ldb.LdbError ERR_NO_SUCH_OBJECT (not a machine of this site), ERR_INSUFFICIENT_ACCESS_RIGHTS.
    Feeds:   directory_ops (op "set_machine")."""
    m = find_machine(samdb, site, name)
    uac = int(str(m.get("userAccountControl", idx=0) or 0))
    want = uac & ~ACCOUNTDISABLE if enabled else uac | ACCOUNTDISABLE
    if want != uac:
        msg = ldb.Message(m.dn)
        msg["userAccountControl"] = ldb.MessageElement([str(want)], ldb.FLAG_MOD_REPLACE, "userAccountControl")
        samdb.modify(msg)
    return {"name": name, "enabled": bool(enabled), "changed": want != uac}
