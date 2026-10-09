#!/usr/bin/env python3
"""Spike (manual 2.3.12.1): convert a published DNS block list into a BIND response policy zone.

    python3 convert.py LIST_FILE ZONE_NAME OUT_ZONE_FILE      prints a JSON summary of what was converted and skipped

Formats, following AdGuard's DNS filtering syntax (adguard-dns.io/kb/general/dns-filtering-syntax):
  hosts         "0.0.0.0 name [name...]"  blocks each name exactly (not its subdomains)
  domains-only  "name"                    blocks the name exactly
  adblock       "||name^"                 blocks the name and every name below it;  "@@||name^" allows them
                "||*.name^", "||tld^"     every name below (a whole top-level domain too)
                "||1.2.3.4^"              any answer holding that address (RPZ rpz-ip)
  modifiers     $important                dropped: fabric's own rules already come first
                $denyallow=a|b            the block, with a, b and their subdomains allowed
                $dnsrewrite=<name>        a block (AdGuard points it at its block page; fabric answers NXDOMAIN)
                $badfilter                cancels the same rule without it, in the same list
Skipped and counted, never guessed: regular expressions, other modifiers ($dnstype, $client, $ctag...),
wildcards inside a name, unanchored patterns ("name^", "|name^" match by prefix), cosmetic rules.
Throwaway (global Rule 4): the product's converter is designed from what this finds.
"""
import ipaddress
import json
import re
import sys

LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$")
HOSTS_ADDR = {"0.0.0.0", "127.0.0.1", "::", "::1", "0:0:0:0:0:0:0:0"}
HOSTS_IGNORED = {"localhost", "localhost.localdomain", "local", "broadcasthost", "ip6-localhost", "ip6-loopback",
                 "0.0.0.0"}
ADBLOCK = re.compile(r"^(@@)?\|\|([^\^$|/]+)\^?(\$(.*))?$")
KNOWN_MODIFIERS = {"important", "denyallow", "dnsrewrite", "badfilter"}


def valid_name(name, single_label=False):
    """A DNS name RPZ can carry as a trigger: lowercase labels (one label only when single_label, a TLD)."""
    name = name.rstrip(".").lower()
    if not name or len(name) > 253:
        return None
    labels = name.split(".")
    if (len(labels) < 2 and not single_label) or not all(LABEL.match(label) for label in labels):
        return None
    return name


def address(text):
    """An IP address rule's address, or None."""
    try:
        return ipaddress.ip_address(text)
    except ValueError:
        return None


def parse(lines):
    """Return (rules, skipped). rules: {"block"|"allow": {name: "exact"|"tree"|"below"}, "ip": set of addresses}."""
    block, allow, ips, bad = {}, {}, set(), set()
    skipped = {}

    def skip(reason):
        skipped[reason] = skipped.get(reason, 0) + 1

    def add(table, name, scope):
        order = {"exact": 0, "below": 1, "tree": 2}
        old = table.get(name)
        if old is None:
            table[name] = scope
        elif {old, scope} == {"exact", "below"}:
            table[name] = "tree"
        elif order[scope] > order[old]:
            table[name] = scope

    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("!") or line.startswith("#") or line.startswith("["):
            continue
        if "##" in line or "#@#" in line or "#$#" in line:
            skip("cosmetic")
            continue
        if line.startswith("/") and line.endswith("/") or line.startswith("@@/"):
            skip("regex")
            continue
        m = ADBLOCK.match(line)
        if m:
            is_allow, pattern, modifiers = bool(m.group(1)), m.group(2).lower(), m.group(4) or ""
            mods = {}
            for part in filter(None, modifiers.split(",")):
                key, _, value = part.partition("=")
                mods[key.strip()] = value.strip()
            if set(mods) - KNOWN_MODIFIERS:
                skip("modifier")
                continue
            if "dnsrewrite" in mods and (is_allow or not valid_name(mods["dnsrewrite"])):
                skip("modifier")          # a rewrite to an address or a record: not a block
                continue
            if "badfilter" in mods:
                bad.add((is_allow, pattern))
                continue
            scope = "tree"
            if pattern.startswith("*."):
                pattern, scope = pattern[2:], "below"
            if "*" in pattern:
                skip("wildcard")
                continue
            ip = address(pattern)
            if ip:
                if is_allow or mods:
                    skip("modifier")
                else:
                    ips.add(ip)
                continue
            name = valid_name(pattern, single_label=True)
            if not name:
                skip("not a name")
                continue
            if (is_allow, m.group(2).lower()) in bad:
                continue
            add(allow if is_allow else block, name, scope)
            for exception in filter(None, mods.get("denyallow", "").split("|")):
                ex = valid_name(exception)
                if ex:
                    add(allow, ex, "tree")
            continue
        if line.startswith("@@") or line.startswith("|") or "^" in line or "$" in line or "*" in line:
            skip("unanchored or other adblock pattern")
            continue
        fields = line.split("#", 1)[0].split()
        if len(fields) >= 2 and fields[0] in HOSTS_ADDR:
            for host in fields[1:]:
                if host in HOSTS_IGNORED:
                    continue
                name = valid_name(host)
                if name:
                    add(block, name, "exact")
                else:
                    skip("not a name")
            continue
        if len(fields) >= 2 and address(fields[0]):
            skip("hosts rule to another address")
            continue
        if len(fields) == 1:
            name = valid_name(fields[0])
            if name:
                add(block, name, "exact")
            else:
                skip("not a name")
            continue
        skip("unrecognised")
    # a $badfilter seen after its rule cancels it too
    for is_allow, pattern in bad:
        table = allow if is_allow else block
        name = pattern[2:] if pattern.startswith("*.") else pattern
        table.pop(name, None)
    return {"block": block, "allow": allow, "ip": ips}, skipped


def covered(name, tree):
    """True when a parent of name is already covered with all its subdomains."""
    labels = name.split(".")
    return any(".".join(labels[i:]) in tree for i in range(1, len(labels)))


def rpz_ip(ip):
    """An address as an RPZ rpz-ip trigger owner name (a /32 or /128)."""
    if ip.version == 4:
        return "32." + ".".join(reversed(str(ip).split("."))) + ".rpz-ip"
    groups = ip.exploded.split(":")
    return "128." + ".".join(reversed([g.lstrip("0") or "0" for g in groups])) + ".rpz-ip"


def write_zone(path, zone, rules):
    """Write the RPZ: allows as passthru, blocks as NXDOMAIN (CNAME .); return the number of RPZ records."""
    block, allow = rules["block"], rules["allow"]
    block_tree = {n for n, s in block.items() if s in ("tree", "below")}
    allow_tree = {n for n, s in allow.items() if s in ("tree", "below")}
    lines = []

    def emit(name, scope, target):
        if scope in ("exact", "tree"):
            lines.append(f"{name} CNAME {target}")
        if scope in ("tree", "below"):
            lines.append(f"*.{name} CNAME {target}")

    for name, scope in sorted(allow.items()):
        emit(name, scope, "rpz-passthru.")
    for name, scope in sorted(block.items()):
        # an exception wins over every block (AdGuard), but in RPZ an exact name beats a wildcard: drop the block
        if covered(name, block_tree) or (name in allow and allow[name] != "below") or covered(name, allow_tree):
            continue
        emit(name, scope, ".")
    for ip in sorted(rules["ip"], key=str):
        lines.append(f"{rpz_ip(ip)} CNAME .")
    with open(path, "w", encoding="ascii") as out:
        out.write(f"$TTL 300\n@ SOA localhost. hostmaster.{zone}. 1 3600 600 86400 300\n@ NS localhost.\n")
        out.write("\n".join(lines) + "\n")
    return len(lines)


def main(argv):
    src, zone, dst = argv
    with open(src, encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    rules, skipped = parse(lines)
    records = write_zone(dst, zone, rules)
    print(json.dumps({"zone": zone, "lines": len(lines), "blocks": len(rules["block"]), "allows": len(rules["allow"]),
                      "ips": len(rules["ip"]), "rpz_records": records, "skipped": sum(skipped.values()),
                      "skipped_by_reason": skipped}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
