def format_value(rtype, record):
    """Right-hand side of a record as it appears in the zone file."""
    if rtype in ("A", "AAAA"):
        return str(record.get("ip", ""))
    if rtype == "CNAME":
        return str(record.get("canonical", ""))
    if rtype == "TXT":
        return f'"{record.get("text", "")}"'
    if rtype == "MX":
        return f"{record.get('priority', '')} {record.get('exchange', '')}"
    if rtype == "SRV":
        return f"{record.get('priority', '')} {record.get('weight', '')} {record.get('port', '')} {record.get('target', '')}"
    return str(record.get("value", record.get("target", "")))
