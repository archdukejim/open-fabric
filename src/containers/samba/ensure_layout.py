import ldb

# every site's OU holds these (manual 1.6.3.4); the root site's also holds OU=organisation
SITE_OUS = ("people", "groups", "machines", "devices", "device-roles", "networks", "sudoers", "service-accounts")
ORGANISATION_OUS = ("groups", "device-roles", "sudoers")
# AD's well-known containers for new users and computers (redirusr, redircmp)
WELL_KNOWN = {"A9D1CA15768811D1ADED00C04FD8D5CD": "people", "AA312825768811D1ADED00C04FD8D5CD": "machines"}


def _ensure_ou(samdb, dn):
    """Purpose: an organisational unit, created when missing.
    Inputs:  samdb — SamDB; dn — str.
    Returns: True if it was created.
    Fails:   ldb.LdbError other than "already exists" (a missing parent, refused).
    Feeds:   ensure_layout."""
    try:
        samdb.add({"dn": dn, "objectClass": "organizationalUnit"})
        return True
    except ldb.LdbError as e:
        if e.args[0] == ldb.ERR_ENTRY_ALREADY_EXISTS:
            return False
        raise


def ensure_layout(samdb, site, root):
    """Purpose: everything fabric manages under OU=sites, one OU per site (D88, manual 1.6.3.4), and AD's default
             containers for new users and computers pointed at the root site's OU=people and OU=machines (so nothing
             Windows' own tools create lands outside OU=sites).
    Inputs:  samdb — SamDB; site — str, this site's name; root — bool, this is the root site (it also holds
             OU=organisation, and the defaults point at it).
    Returns: list of str, what was created or changed.
    Fails:   ldb.LdbError from an addition or modification AD refuses.
    Feeds:   converge."""
    base = str(samdb.domain_dn())
    site_dn = f"OU={site},OU=sites,{base}"
    done = []
    wanted = [f"OU=sites,{base}", site_dn] + [f"OU={ou},{site_dn}" for ou in SITE_OUS]
    if root:
        wanted += [f"OU=organisation,{site_dn}"] + [f"OU={ou},OU=organisation,{site_dn}" for ou in ORGANISATION_OUS]
    done += [dn for dn in wanted if _ensure_ou(samdb, dn)]
    if root:
        res = samdb.search(base=base, scope=ldb.SCOPE_BASE, attrs=["wellKnownObjects"])
        for value in [str(x) for x in res[0].get("wellKnownObjects", [])]:
            guid = value.split(":")[2]
            if guid not in WELL_KNOWN:
                continue
            target = f"OU={WELL_KNOWN[guid]},{site_dn}"
            current = value.split(":", 3)[3]
            if current.lower() == target.lower():
                continue
            # the value is replaced in one modify, as Windows' redirusr/redircmp do
            samdb.modify_ldif(f"dn: {base}\nchangetype: modify\ndelete: wellKnownObjects\nwellKnownObjects: {value}\n"
                              f"-\nadd: wellKnownObjects\nwellKnownObjects: B:32:{guid}:{target}\n")
            done.append(f"new {WELL_KNOWN[guid]} go to {target}")
    return done
