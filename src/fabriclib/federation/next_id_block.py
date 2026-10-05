from fabriclib.samba.domain_id_blocks import domain_id_blocks
from fabriclib.samba.id_range import id_range


def next_id_block(v, registry, container="samba"):
    """Purpose: the uid/gid block a new site gets at its join (D97, manual 1.6.3.9): the next posix_id_block numbers
             after every block the domain holds (each site OU's, read from this site's DC: a parent that is not the
             root does not know the other branches' sites), this site's own and those its registry recorded.
    Inputs:  v — this site's vars (its block: id_range; posix_id_block); registry — load_registry()'s dict;
             container — this site's DC.
    Returns: str "first-last".
    Fails:   ValueError for a malformed block; ValidationError when the DC cannot be read.
    Feeds:   accept_join.
    Notes:   two parents handing out blocks while cut off from each other could pick the same one; AD replicates
             each site's block, so it is seen as soon as the link returns (manual 1.8.8.14)."""
    size = int(v.get("posix_id_block") or 100000)
    blocks = [id_range(v)] + domain_id_blocks(container)
    blocks += [str(s["id_range"]) for s in registry.get("sites", {}).values() if s.get("id_range")]
    first = max(int(b.split("-")[1]) for b in blocks) + 1
    return f"{first}-{first + size - 1}"
