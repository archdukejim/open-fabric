def kea_option_defs(defs):
    """Purpose: Kea's option-def list from dhcp.option_defs (as normalize_option_defs returns them).
    Inputs:  defs — list of {name, code, type, space, array, record_types}, or None.
    Returns: list of Kea option-def dicts (name, code, type, space — dhcp4 by default —, array, record-types).
    Fails:   never.
    Feeds:   jinja_env global kea_option_defs (kea/kea-dhcp4.conf.j2)."""
    out = []
    for d in defs or []:
        entry = {"name": d["name"], "code": d["code"], "type": d["type"], "space": d.get("space", "dhcp4"),
                 "array": bool(d.get("array"))}
        if d.get("record_types"):
            entry["record-types"] = d["record_types"]
        out.append(entry)
    return out
