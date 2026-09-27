def zone_name(data, key):
    """Zone key in vars.yaml -> zone name; `dynamic_zone_var` is the main domain."""
    return data.get("domain", "") if key == "dynamic_zone_var" else key
