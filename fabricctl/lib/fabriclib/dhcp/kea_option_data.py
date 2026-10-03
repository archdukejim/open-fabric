def _key(o):
    """Purpose: what makes two options the same option.
    Inputs:  o — an option (fabric's or Kea's form).
    Returns: (name or code, space).
    Fails:   never.
    Feeds:   kea_option_data."""
    return o.get("name", o.get("code")), o.get("space", "dhcp4")


def kea_option_data(defaults, options):
    """Purpose: Kea's option-data list for one level (global, class, subnet, reservation): the options fabric sets
             itself there, with the admin's options of the same name replacing them, then the admin's others.
    Inputs:  defaults — fabric's own options at that level ([{name, data}], e.g. domain-name-servers, routers);
             options — the admin's options as normalize_options returns them (None: none).
    Returns: list of Kea option-data dicts (name or code, data, space when not dhcp4, csv-format, always-send).
    Fails:   never (the options were checked by normalize_dhcp).
    Feeds:   jinja_env global kea_option_data (kea/kea-dhcp4.conf.j2), dhcp/dhcp_overview (overrides shown)."""
    mine = list(options or [])
    replaced = {_key(o) for o in mine}
    out = [dict(o) for o in defaults if _key(o) not in replaced]
    for o in mine:
        entry = {k: o[k] for k in ("name", "code", "data", "space") if k in o}
        if "csv_format" in o:
            entry["csv-format"] = o["csv_format"]
        if "always_send" in o:
            entry["always-send"] = o["always_send"]
        out.append(entry)
    return out
