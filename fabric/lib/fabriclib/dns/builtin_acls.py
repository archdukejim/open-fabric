def builtin_acls(data):
    """The ACLs fabric always renders (vars.yaml.j2 merges user entries over
    these), so they and their entries cannot be removed."""
    subnet = data.get("fabric_subnet") or "10.255.0.0/24"
    return {
        "acme-updaters": [subnet],
        "dns-resolvers": ["127.0.0.1", data.get("lan_cidr"), subnet],
    }
