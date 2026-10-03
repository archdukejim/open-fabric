import os

from fabriclib.common.paths import FEDERATION_FILE
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.ca_path_len import ca_path_len


def signing_capacity(v, registry_path=FEDERATION_FILE):
    """Purpose: how this install signs a joining site's CA and how deep the sites it signs may nest (manual 1.8.5.1): the root site signs with the root key, a site that joined an upstream with its
             own intermediate.
    Inputs:  v — fabric vars: deploy_base_dir (the CA certificates); registry_path — default FEDERATION_FILE.
    Returns: {"as_parent": False for the root site (no upstream recorded), True for a site; "max_nest": the
             largest --nest a site it signs may get (None: no limit; -1: it cannot sign sites at all)}. The
             signer's path length minus one: a root of path length 2 allows --nest 1; a site CA of path
             length 0 signs no sites.
    Fails:   OSError / ValidationError when the CA certificate cannot be read or parsed.
    Feeds:   create_invitation, accept_join."""
    as_parent = bool(load_registry(registry_path)["upstream"])
    root, ica = ca_files(v)
    with open(ica if as_parent else root) as f:
        depth = ca_path_len(f.read())
    return {"as_parent": as_parent, "max_nest": None if depth is None else depth - 1}
