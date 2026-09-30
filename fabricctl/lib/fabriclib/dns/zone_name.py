def zone_name(data, key):
    """Purpose: Turn a zone key in vars.yaml into the zone's name.
    Inputs:  data — the vars dict (reads domain); key — str zone key.
    Returns: str: the main domain for "dynamic_zone_var", else the key itself.
    Fails:   never.
    Feeds:   list_zones, reverse_zones, zone_detail (bind9/config/named.conf.zones.j2 does the same in Jinja).
    """
    return data.get("domain", "") if key == "dynamic_zone_var" else key
