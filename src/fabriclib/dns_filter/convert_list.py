import ipaddress
import re

LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
HOSTS_ADDR = {"0.0.0.0", "127.0.0.1", "::", "::1", "0:0:0:0:0:0:0:0"}
HOSTS_IGNORED = {"localhost", "localhost.localdomain", "local", "broadcasthost", "ip6-localhost", "ip6-loopback",
                 "0.0.0.0"}
ADBLOCK = re.compile(r"^(@@)?\|\|([^\^$|/]+)\^?(\$(.*))?$")
KNOWN_MODIFIERS = {"important", "denyallow", "dnsrewrite", "badfilter"}
ORDER = {"exact": 0, "below": 1, "tree": 2}


def _name(text, single_label=False):
    """Purpose: a DNS name RPZ can carry as a trigger.
    Inputs:  text — a name from a list; single_label — True to accept one label (a whole TLD).
    Returns: the lowercased name without a trailing dot, or None when it is not one (bad labels, too long, a
             single label when not allowed).
    Fails:   never.
    Feeds:   _parse_line."""
    name = text.rstrip(".").lower()
    if not name or len(name) > 253:
        return None
    labels = name.split(".")
    if (len(labels) < 2 and not single_label) or not all(LABEL.match(label) for label in labels):
        return None
    return name


def _address(text):
    """Purpose: an IP address rule's address.
    Inputs:  text — str.
    Returns: an ipaddress object, or None when text is not an address.
    Fails:   never.
    Feeds:   _parse_line."""
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def _add(table, name, scope):
    """Purpose: record a name in the block or allow table, widening its scope when it is seen again.
    Inputs:  table — dict name → "exact" | "below" | "tree" (changed in place); name — str; scope — one of those.
    Returns: None.
    Fails:   never.
    Feeds:   _parse_line."""
    old = table.get(name)
    if old is None:
        table[name] = scope
    elif {old, scope} == {"exact", "below"}:
        table[name] = "tree"
    elif ORDER[scope] > ORDER[old]:
        table[name] = scope


def _parse_adblock(match, rules, skip):
    """Purpose: one AdGuard DNS-syntax rule (`||name^`, `@@||name^`, with modifiers) into the rules.
    Inputs:  match — ADBLOCK's match; rules — the tables being built (block, allow, ip, bad); skip — callable(reason).
    Returns: None.
    Fails:   never.
    Feeds:   _parse_line."""
    is_allow, pattern, modifiers = bool(match.group(1)), match.group(2).lower(), match.group(4) or ""
    mods = {}
    for part in filter(None, modifiers.split(",")):
        key, _, value = part.partition("=")
        mods[key.strip()] = value.strip()
    if set(mods) - KNOWN_MODIFIERS:
        return skip("modifier")
    if "dnsrewrite" in mods and (is_allow or not _name(mods["dnsrewrite"])):
        return skip("modifier")              # a rewrite to an address or a record, not a block
    if "badfilter" in mods:
        rules["bad"].add((is_allow, pattern))
        return None
    scope = "tree"
    if pattern.startswith("*."):
        pattern, scope = pattern[2:], "below"
    if "*" in pattern:
        return skip("wildcard inside a name")
    ip = _address(pattern)
    if ip:
        if is_allow or mods:
            return skip("modifier")
        rules["ip"].add(ip)
        return None
    name = _name(pattern, single_label=True)
    if not name:
        return skip("not a name")
    _add(rules["allow"] if is_allow else rules["block"], name, scope)
    for exception in filter(None, mods.get("denyallow", "").split("|")):
        ex = _name(exception)
        if ex:
            _add(rules["allow"], ex, "tree")
    return None


def _parse_line(raw, rules, skip):
    """Purpose: one line of a list (hosts, plain domain, AdGuard DNS syntax) into the rules.
    Inputs:  raw — the line; rules — the tables being built; skip — callable(reason) counting what is not converted.
    Returns: None.
    Fails:   never.
    Feeds:   convert_list."""
    line = raw.strip()
    if not line or line[0] in "!#[":
        return None
    if "##" in line or "#@#" in line or "#$#" in line:
        return skip("cosmetic")
    if (line.startswith("/") and line.endswith("/")) or line.startswith("@@/"):
        return skip("regular expression")
    match = ADBLOCK.match(line)
    if match:
        return _parse_adblock(match, rules, skip)
    if line.startswith("@@") or line.startswith("|") or any(c in line for c in "^$*"):
        return skip("unanchored pattern")
    fields = line.split("#", 1)[0].split()
    if len(fields) >= 2 and fields[0] in HOSTS_ADDR:
        for host in fields[1:]:
            if host not in HOSTS_IGNORED:
                name = _name(host)
                _add(rules["block"], name, "exact") if name else skip("not a name")
        return None
    if len(fields) >= 2 and _address(fields[0]):
        return skip("hosts rule to another address")
    if len(fields) == 1:
        name = _name(fields[0])
        return _add(rules["block"], name, "exact") if name else skip("not a name")
    return skip("unrecognised")


def _covered(name, tree):
    """Purpose: whether a parent of name already covers it with every name below.
    Inputs:  name — str; tree — set of names covered with their subdomains.
    Returns: bool.
    Fails:   never.
    Feeds:   _records."""
    labels = name.split(".")
    return any(".".join(labels[i:]) in tree for i in range(1, len(labels)))


def _rpz_ip(ip):
    """Purpose: an address as an RPZ rpz-ip trigger owner name (/32 or /128).
    Inputs:  ip — an ipaddress object.
    Returns: str, e.g. "32.4.3.2.1.rpz-ip".
    Fails:   never.
    Feeds:   _records."""
    if ip.version == 4:
        return "32." + ".".join(reversed(str(ip).split("."))) + ".rpz-ip"
    return "128." + ".".join(reversed([g.lstrip("0") or "0" for g in ip.exploded.split(":")])) + ".rpz-ip"


def _records(rules):
    """Purpose: the RPZ records for the rules: allows as passthru, blocks as NXDOMAIN (`CNAME .`).
    Inputs:  rules — the tables (block, allow, ip).
    Returns: list of record lines, without the SOA and NS.
    Fails:   never.
    Notes:   an allow beats every block (AdGuard), but in RPZ an exact name beats a wildcard, so a block inside an
             allowed tree is left out rather than written; a block under a blocked tree is redundant and left out.
    Feeds:   convert_list."""
    block, allow = rules["block"], rules["allow"]
    block_tree = {n for n, s in block.items() if s in ("tree", "below")}
    allow_tree = {n for n, s in allow.items() if s in ("tree", "below")}
    lines = []

    def emit(name, scope, target):
        """Purpose: the name's record and/or its wildcard's, by scope.
        Inputs:  name — str; scope — "exact" | "below" | "tree"; target — "." or "rpz-passthru.".
        Returns: None (appends to lines).
        Fails:   never.
        Feeds:   _records."""
        if scope in ("exact", "tree"):
            lines.append(f"{name} CNAME {target}")
        if scope in ("tree", "below"):
            lines.append(f"*.{name} CNAME {target}")

    for name, scope in sorted(allow.items()):
        emit(name, scope, "rpz-passthru.")
    for name, scope in sorted(block.items()):
        if _covered(name, block_tree) or (name in allow and allow[name] != "below") or _covered(name, allow_tree):
            continue
        emit(name, scope, ".")
    for ip in sorted(rules["ip"], key=str):
        lines.append(f"{_rpz_ip(ip)} CNAME .")
    return lines


def convert_list(text, zone):
    """Purpose: convert a published DNS block list into a response policy zone (manual 1.12.2.6): hosts files, plain
             domains, RPZ as published, and AdGuard's DNS syntax — `||name^` (the name and below), `@@||name^`,
             `||*.name^`, a whole TLD, `$denyallow`, `$dnsrewrite` to a name (a block), `$badfilter`, `$important`,
             `||1.2.3.4^` (an rpz-ip trigger). What RPZ cannot express is skipped and counted, never guessed.
    Inputs:  text — the list as downloaded (str); zone — the zone's name (e.g. "<id>.list.rpz").
    Returns: {"zone_text": the zone file (str), "rules": rules converted (block + allow names + addresses),
             "records": RPZ records written, "skipped": rules skipped, "skipped_by_reason": {reason: count}}.
    Fails:   never (an empty or unusable list gives rules 0: the caller refuses it).
    Feeds:   dns_filter/update_lists; tests/resolver/run.py.
    Notes:   AdGuard's semantics (adguard-dns.io/kb/general/dns-filtering-syntax): a hosts line or a plain domain
             blocks the name only; `||name^` the name and every name below it. An RPZ list as published (lines
             "name CNAME .") is read as plain domains: its wildcard lines become `*.name` blocks."""
    rules = {"block": {}, "allow": {}, "ip": set(), "bad": set()}
    skipped = {}

    def skip(reason):
        """Purpose: count a rule that is not converted.
        Inputs:  reason — str.
        Returns: None.
        Fails:   never.
        Feeds:   _parse_line, _parse_adblock."""
        skipped[reason] = skipped.get(reason, 0) + 1

    for raw in text.splitlines():
        rpz = raw.split()
        if len(rpz) == 3 and rpz[1].upper() == "CNAME" and rpz[2] in (".", "rpz-passthru."):
            name = rpz[0].rstrip(".").lower()
            scope = "below" if name.startswith("*.") else "exact"
            name = _name(name[2:] if scope == "below" else name, single_label=True)    # a whole TLD too
            if name:
                _add(rules["allow"] if rpz[2] == "rpz-passthru." else rules["block"], name, scope)
            else:
                skip("not a name")
            continue
        # an RPZ file's header ("@ SOA", "@ NS", "$TTL", comments); "@@||name^" is an allow rule, not a header
        if raw.lstrip().startswith(("$TTL", "@ ", "@\t", ";")) or (len(rpz) > 2 and rpz[1].upper() in ("SOA", "NS")):
            continue
        _parse_line(raw, rules, skip)
    for is_allow, pattern in rules["bad"]:        # $badfilter cancels its rule wherever it stands
        table = rules["allow"] if is_allow else rules["block"]
        table.pop(pattern[2:] if pattern.startswith("*.") else pattern, None)
    records = _records(rules)
    head = f"$TTL 300\n@ SOA localhost. hostmaster.{zone}. 1 3600 600 86400 300\n@ NS localhost.\n"
    return {"zone_text": head + "".join(f"{line}\n" for line in records),
            "rules": len(rules["block"]) + len(rules["allow"]) + len(rules["ip"]),
            "records": len(records), "skipped": sum(skipped.values()), "skipped_by_reason": skipped}
