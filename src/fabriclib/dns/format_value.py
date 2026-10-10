def format_value(rtype, record):
    """Purpose: The right-hand side of a record as it appears in the zone file, for display.
    Inputs:  rtype — str record type.
             record — the stored record dict (ip, canonical, text, priority, exchange, weight, port, target, value).
    Returns: str: the IP (A/AAAA), canonical name (CNAME), quoted text (TXT), "priority exchange" (MX), "priority weight
             port target" (SRV), else value or target; missing fields render as "".
    Fails:   never — dict reads with defaults.
    Feeds:   zone_detail; the zone editor (menu/edit_dns_zone).
    """
    if rtype in ("A", "AAAA"):
        return str(record.get("ip", ""))
    if rtype == "CNAME":
        return str(record.get("canonical", ""))
    if rtype == "TXT":
        return f'"{record.get("text", "")}"'
    if rtype == "MX":
        return f"{record.get('priority', '')} {record.get('exchange', '')}"
    if rtype == "SRV":
        target = record.get("target", "")        # one line: an f-string split inside {…} needs Python 3.12
        return f"{record.get('priority', '')} {record.get('weight', '')} {record.get('port', '')} {target}"
    return str(record.get("value", record.get("target", "")))
