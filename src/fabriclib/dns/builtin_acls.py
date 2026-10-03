def builtin_acls(data):
    """Purpose: The ACLs fabric always renders (vars.yaml.j2 merges user entries over them), so they and their entries
             cannot be removed.
    Inputs:  data — the vars dict; reads fabric_subnet (default 10.255.0.0/24) and lan_cidr.
    Returns: {"acme-updaters": [subnet], "dns-resolvers": ["127.0.0.1", lan_cidr, subnet]} (lan_cidr may be None).
    Fails:   never — plain dict reads.
    Feeds:   remove_acl_entries (refuses to remove them), run_acl_command (marks them "built in" in `acl list`).
    """
    subnet = data.get("fabric_subnet") or "10.255.0.0/24"
    return {
        "acme-updaters": [subnet],
        "dns-resolvers": ["127.0.0.1", data.get("lan_cidr"), subnet],
    }
