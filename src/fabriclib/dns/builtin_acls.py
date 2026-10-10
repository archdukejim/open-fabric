from fabriclib.dhcp.client_networks import client_networks


def builtin_acls(data):
    """Purpose: The ACLs fabric always renders (vars.yaml.j2 merges user entries over them), so they and their entries
             cannot be removed.
    Inputs:  data — the vars dict; reads fabric_subnet (default 10.255.0.0/24), lan_cidr, and DHCP's full subnets
             (client_networks: their clients resolve through fabric like the LAN's, 2.1.10.4).
    Returns: {"acme-updaters": [subnet], "dns-resolvers": ["127.0.0.1", lan_cidr, subnet, *DHCP's full subnets]}
             (lan_cidr may be None).
    Fails:   never — plain dict reads.
    Feeds:   remove_acl_entries (refuses to remove them), run_acl_command (marks them "built in" in `acl list`).
    """
    subnet = data.get("fabric_subnet") or "10.255.0.0/24"
    return {
        "acme-updaters": [subnet],
        "dns-resolvers": ["127.0.0.1", data.get("lan_cidr"), subnet, *client_networks(data)["full"]],
    }
