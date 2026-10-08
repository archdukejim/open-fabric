from fabriclib.samba.domain_sites import domain_sites
from fabriclib.samba.id_range import id_range


def next_id_block(v, registry, container="samba", sites=None):
    """Purpose: the uid/gid block a new site gets at its join (D97, manual 1.6.3.9): the next posix_id_block numbers
             after every block the domain holds (each site OU's, read from this site's DC: a parent that is not the
             root does not know the other branches' sites), this site's own and those its registry recorded.
    Inputs:  v — this site's vars (its block: id_range; posix_id_block); registry — load_registry()'s dict;
             container — this site's DC; sites — domain_sites()'s list when the caller read it already.
    Returns: str "first-last".
    Fails:   ValueError for a malformed block; ValidationError when the DC cannot be read.
    Feeds:   accept_join.
    Notes:   two parents handing out blocks while cut off from each other could pick the same one; AD replicates
             each site's block, so it is seen as soon as the link returns (manual 1.6.3.9)."""
    size = int(v.get("posix_id_block") or 100000)
    held = domain_sites(container) if sites is None else sites
    blocks = [id_range(v)] + [s["id_range"] for s in held if s.get("id_range")]
    blocks += [str(s["id_range"]) for s in registry.get("sites", {}).values() if s.get("id_range")]
    first = max(int(b.split("-")[1]) for b in blocks) + 1
    return f"{first}-{first + size - 1}"
