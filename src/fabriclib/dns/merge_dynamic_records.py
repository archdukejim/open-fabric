TYPES = {"PTR", "DHCID"}          # what Kea writes in a reverse zone (2.1.10.7)
CLASSES = {"IN", "CH", "HS"}


def _records(text, zone):
    """Purpose: the PTR and DHCID records of a zone file, owners made absolute.
    Inputs:  text — a zone file as fabric renders it or BIND writes it ($ORIGIN, relative owners, an owner left out
             to repeat the last, TTL and class optional, comments); zone — its name.
    Returns: list of (owner FQDN with trailing dot, lower-case; type; rdata as written).
    Fails:   never: lines it cannot read are skipped.
    Feeds:   merge_dynamic_records."""
    origin, owner, out, depth = zone.rstrip(".") + ".", None, [], 0
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].rstrip()
        if not line.strip():
            continue
        if depth:                                    # inside ( ... ), e.g. the SOA
            depth += line.count("(") - line.count(")")
            continue
        if line.startswith("$ORIGIN"):
            origin = line.split()[1].rstrip(".") + "."
            continue
        if line.startswith("$"):
            continue
        tokens = line.split()
        if not raw[:1].isspace():
            owner = tokens.pop(0)
            owner = origin if owner == "@" else owner if owner.endswith(".") else f"{owner}.{origin}"
        while tokens and (tokens[0].isdigit() or tokens[0].upper() in CLASSES):
            tokens.pop(0)
        depth = line.count("(") - line.count(")")
        if owner and len(tokens) >= 2 and tokens[0].upper() in TYPES:
            out.append((owner.lower(), tokens[0].upper(), " ".join(tokens[1:])))
    return out


def merge_dynamic_records(zone, new_text, old_text):
    """Purpose: keep the PTR and DHCID records Kea wrote in a reverse zone when fabric installs its regenerated file
             (2.1.10.7, manual 1.10.3.4): the old file holds them once BIND has been frozen (it writes its copy).
    Inputs:  zone — the reverse zone's name; new_text — fabric's regenerated file; old_text — the file being replaced
             (as BIND wrote it), or "" when there is none.
    Returns: new_text with the old file's PTR and DHCID records appended (absolute owners) for every owner the new
             file has no PTR for; new_text unchanged when there are none. Fabric's own PTRs win.
    Fails:   never.
    Feeds:   dns/install_zone_file (reverse zones)."""
    static = {o for o, t, _ in _records(new_text, zone) if t == "PTR"}
    keep = [r for r in _records(old_text or "", zone) if r[0] not in static]
    if not keep:
        return new_text
    lines = [f"{o:<40} {t:<6} {d}" for o, t, d in keep]
    head = "\n\n; kept from DHCP's registrations (Kea's key; 2.1.10.7)\n"
    return new_text.rstrip("\n") + head + "\n".join(lines) + "\n"
