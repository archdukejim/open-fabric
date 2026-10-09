import os


def resolver_paths(v):
    """Purpose: the BIND resolver's folders and files under the deploy base (manual 1.12.2.4).
    Inputs:  v — fabric vars (deploy_base_dir, default /opt).
    Returns: {"root", "config", "lists", "log", "cache": folders; "state": the lists' state file
             (lists/state.json)}.
    Fails:   never.
    Feeds:   dns_filter/deploy_resolver, dns_filter/update_lists, dns_filter/show_filter_status."""
    root = os.path.join(v.get("deploy_base_dir") or "/opt", "resolver")
    return {"root": root, "config": os.path.join(root, "config"), "lists": os.path.join(root, "lists"),
            "log": os.path.join(root, "log"), "cache": os.path.join(root, "cache"),
            "state": os.path.join(root, "lists", "state.json")}
