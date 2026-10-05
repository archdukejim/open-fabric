def id_range(v):
    """Purpose: this site's uid/gid block (D97, manual 1.6.3.9) as "first-last": the root site's starts where fabric's
             people range always started (the users OU's uid_range, 5001 by default), so earlier numbers stay valid,
             and is posix_id_block numbers long. (A site's block comes from the root at its join: S8.)
    Inputs:  v — rendered vars: ldap_organizational_units (the users OU's uid_range), posix_id_block.
    Returns: str "first-last".
    Fails:   ValueError for a malformed uid_range.
    Feeds:   converge_domain."""
    users = next((o for o in v.get("ldap_organizational_units") or [] if o.get("name") == "users"), {})
    first = int(str(users.get("uid_range") or "5001-50000").split("-")[0])
    return f"{first}-{first + int(v.get('posix_id_block') or 100000) - 1}"
