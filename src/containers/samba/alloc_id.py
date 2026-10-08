import ldb


def alloc_id(samdb, site_dn):
    """Purpose: the next uid/gid number of a site's block, never handed out twice (D97, manual 1.6.3.9): the site's
             high-water mark `fabricIdNext` is moved forward with one conditional change (delete the value read, add
             the next), so two writers cannot take the same number; a refused change is read and tried again.
    Inputs:  samdb — SamDB (the system's, or a connection as an account allowed to change the site's OU); site_dn —
             str, the site's OU.
    Returns: int, the number taken.
    Fails:   ValueError "the id block … is full" when the mark has passed the block's end; ldb.LdbError after five
             refused tries or for a missing OU.
    Feeds:   converge (site groups), the directory operations (people, groups)."""
    for _ in range(5):
        res = samdb.search(base=site_dn, scope=ldb.SCOPE_BASE, attrs=["fabricIdRange", "fabricIdNext"])[0]
        first, last = (int(x) for x in str(res["fabricIdRange"][0]).split("-"))
        nxt = int(str(res["fabricIdNext"][0]))
        if nxt > last:
            raise ValueError(f"the id block {first}-{last} of {site_dn} is full")
        try:
            samdb.modify_ldif(f"dn: {site_dn}\nchangetype: modify\ndelete: fabricIdNext\nfabricIdNext: {nxt}\n-\n"
                              f"add: fabricIdNext\nfabricIdNext: {nxt + 1}\n")
            return nxt
        except ldb.LdbError as e:
            if e.args[0] != ldb.ERR_NO_SUCH_ATTRIBUTE:      # another writer moved the mark first: read again
                raise
    raise ldb.LdbError(ldb.ERR_OTHER, f"could not take an id from {site_dn}: too many writers at once")
