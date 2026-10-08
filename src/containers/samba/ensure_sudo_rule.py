import ldb

import paths
from site_roles import role_group

MARK = "fabric: the site's linux-sudo role (2.1.9.13)"
OLD_MARK = "fabric: the site's admins (2.1.9.13)"      # the rule before the roles: named <site>-admins


def ensure_sudo_rule(samdb, site, admin_group, root=False):
    """Purpose: the site's default sudo rule (manual 1.6.5.19, S6.3; 2.1.9.13): members of `<site>-linux-sudo` (and, at
             the root site, the organisation's admin group) may run any command as root on the site's joined Linux
             machines, and on those of every site below it (their installer reads the rules of each site above,
             1.6.7.4). Kept to match; other rules in OU=sudoers are the admins' and never touched, except fabric's
             own rule from before the roles, which it removes.
    Inputs:  samdb — SamDB (as the system); site — str; admin_group — the web UI's admin group (sAMAccountName);
             root — bool, the root site.
    Returns: list of str, what changed.
    Fails:   ldb.LdbError for a change AD refuses (OU=sudoers missing: ensure_layout makes it first).
    Feeds:   converge."""
    sudoers = f"OU=sudoers,{paths.site_dn(samdb, site)}"
    done = []
    old = f"CN={site}-admins,{sudoers}"
    if _exists(samdb, old) and str(samdb.search(base=old, scope=ldb.SCOPE_BASE, attrs=["description"])[0]
                                   .get("description", [""])[0]) == OLD_MARK:
        samdb.delete(old)
        done.append(f"sudo rule {site}-admins removed (the role {role_group(site, 'linux-sudo')} replaces it)")
    dn = f"CN={role_group(site, 'linux-sudo')},{sudoers}"
    users = {f"%{role_group(site, 'linux-sudo')}"} | ({f"%{admin_group}"} if root else set())
    want = {"sudoUser": sorted(users), "sudoHost": ["ALL"], "sudoCommand": ["ALL"], "sudoRunAsUser": ["ALL"],
            "description": [MARK]}
    found = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=list(want)) if _exists(samdb, dn) else []
    if not found:
        samdb.add({"dn": dn, "objectClass": "sudoRole", **want})
        return done + [f"sudo rule {role_group(site, 'linux-sudo')} added"]
    msg = ldb.Message(found[0].dn)
    for attr, val in want.items():
        if sorted(str(x) for x in found[0].get(attr, [])) != sorted(val):
            msg[attr] = ldb.MessageElement(val, ldb.FLAG_MOD_REPLACE, attr)
    if len(msg) == 0:
        return done
    samdb.modify(msg)
    return done + [f"sudo rule {role_group(site, 'linux-sudo')} changed"]


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
