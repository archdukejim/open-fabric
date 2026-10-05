from fabriclib.samba.id_range import id_range


def next_id_block(v, registry):
    """Purpose: the uid/gid block a new site gets at its join (D97, manual 1.6.3.9): the next posix_id_block numbers
             after the root's block and every block handed out before (recorded in the registry's sites).
    Inputs:  v — the root's vars (its block: id_range; posix_id_block); registry — load_registry()'s dict.
    Returns: str "first-last".
    Fails:   ValueError for a malformed block.
    Feeds:   accept_join."""
    size = int(v.get("posix_id_block") or 100000)
    ends = [int(id_range(v).split("-")[1])]
    ends += [int(str(s["id_range"]).split("-")[1]) for s in registry.get("sites", {}).values() if s.get("id_range")]
    first = max(ends) + 1
    return f"{first}-{first + size - 1}"
