import ldb

import paths

MARK = "fabric: the site's admins (D103)"


def ensure_sudo_rule(samdb, site, admin_group):
    """Purpose: the site's default sudo rule (manual 2.11.2.19, S6.3; D103): `<site>-admins` and the organisation's
             admin group may run any command as root on the site's joined Linux machines. Kept to match; other rules
             in OU=sudoers are the admins' and never touched.
    Inputs:  samdb — SamDB (as the system); site — str; admin_group — the web UI's admin group (sAMAccountName).
    Returns: list of str, what changed.
    Fails:   ldb.LdbError for a change AD refuses (OU=sudoers missing: ensure_layout makes it first).
    Feeds:   converge."""
    dn = f"CN={site}-admins,OU=sudoers,{paths.site_dn(samdb, site)}"
    want = {"sudoUser": sorted({f"%{site}-admins", f"%{admin_group}"}), "sudoHost": ["ALL"], "sudoCommand": ["ALL"],
            "sudoRunAsUser": ["ALL"], "description": [MARK]}
    found = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=list(want)) if _exists(samdb, dn) else []
    if not found:
        samdb.add({"dn": dn, "objectClass": "sudoRole", **want})
        return [f"sudo rule {site}-admins added"]
    msg = ldb.Message(found[0].dn)
    for attr, val in want.items():
        if sorted(str(x) for x in found[0].get(attr, [])) != sorted(val):
            msg[attr] = ldb.MessageElement(val, ldb.FLAG_MOD_REPLACE, attr)
    if len(msg) == 0:
        return []
    samdb.modify(msg)
    return [f"sudo rule {site}-admins changed"]


def _exists(samdb, dn):
    """Purpose: whether an entry exists.
    Inputs:  samdb — SamDB; dn — str.
    Returns: bool.
    Fails:   ldb.LdbError other than no such object.
    Feeds:   ensure_sudo_rule."""
    try:
        samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=["dn"])
        return True
    except ldb.LdbError as e:
        if e.args[0] == ldb.ERR_NO_SUCH_OBJECT:
            return False
        raise
