import ldb


def ensure_site_info(samdb, site, id_range):
    """Purpose: a site's uid/gid block on its OU (D97, manual 1.6.3.9): `fabricIdRange` "first-last" and the
             high-water mark `fabricIdNext`, starting at the block's first number. The block is set once: a site never
             changes its block (ids already handed out stay valid), and the mark only moves forward (alloc_id).
    Inputs:  samdb — SamDB; site — str; id_range — str "first-last" (the root's: from today's range start; a site's:
             from the root at its join).
    Returns: list of str, what was added or set.
    Fails:   ldb.LdbError from a change AD refuses; ValueError for a malformed id_range.
    Feeds:   converge."""
    first, last = (int(x) for x in id_range.split("-"))
    if not 0 < first <= last:
        raise ValueError(f"id range {id_range!r}: first-last, both positive")
    dn = f"OU={site},OU=sites,{samdb.domain_dn()}"
    have = samdb.search(base=dn, scope=ldb.SCOPE_BASE, attrs=["objectClass", "fabricIdRange", "fabricIdNext"])[0]
    changes, done = {}, []
    if "fabricSiteInfo" not in [str(c) for c in have["objectClass"]]:
        # the class first, on its own: AD checks a change's attributes against the classes the entry already has
        samdb.modify(ldb.Message.from_dict(samdb, {"dn": dn, "objectClass": "fabricSiteInfo"}, ldb.FLAG_MOD_ADD))
        done.append(f"site {site}: objectClass fabricSiteInfo added")
    if "fabricIdRange" not in have:
        changes["fabricIdRange"] = id_range
    if "fabricIdNext" not in have:
        changes["fabricIdNext"] = str(first)
    if changes:
        samdb.modify(ldb.Message.from_dict(samdb, {"dn": dn, **changes}, ldb.FLAG_MOD_REPLACE))
    return done + [f"site {site}: {k} set" for k in sorted(changes)]
