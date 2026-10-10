import ipaddress
import re

from fabriclib.common.errors import ValidationError
from fabriclib.dns_filter.common.rule_names import rule_names

GROUP_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,30}[a-z0-9])?$")
YOUTUBE = ("strict", "moderate")
# never a group's: fabric's own containers, and the chain's hop from a group's view to the main view (127.0.0.1)
LOOPBACK = ipaddress.ip_network("127.0.0.0/8")


def _clients(raw, name, answered, fabric):
    """Purpose: one group's clients, checked: IPv4 addresses and subnets the resolver answers, outside fabric's own.
    Inputs:  raw — the setting's value; name — the group (for the messages); answered — the networks the resolver
             answers (ip_network list); fabric — fabric's own networks (ip_network list).
    Returns: list of str, normalised ("192.168.4.50/32" as "192.168.4.50"), without duplicates.
    Fails:   ValidationError for an empty list, an address that is not one, IPv6, host bits set, an address outside
             the answered networks or inside fabric's own.
    Feeds:   check_filter_groups."""
    if not isinstance(raw, list) or not raw:
        raise ValidationError(f"group {name}: clients must list at least one address or subnet")
    out = []
    for item in raw:
        text = str(item).strip()
        try:
            net = ipaddress.ip_network(text, strict=True)
        except ValueError as e:
            raise ValidationError(f"group {name}: {text!r} is not an address or a subnet ({e})") from None
        if net.version != 4:
            raise ValidationError(f"group {name}: {text}: the resolver answers IPv4 clients only")
        if any(net.overlaps(f) for f in fabric):
            raise ValidationError(f"group {name}: {text} overlaps fabric's own network, which is never in a group")
        if not any(net.subnet_of(a) for a in answered):
            raise ValidationError(f"group {name}: {text} is outside the networks the resolver answers "
                                  f"({', '.join(map(str, answered))})")
        out.append(str(net.network_address) if net.prefixlen == 32 else str(net))
    return list(dict.fromkeys(out))


def check_filter_groups(v, own, shared_urls):
    """Purpose: the DNS filter's client groups (manual 1.12.2.15), checked and normalised in place.
    Inputs:  v — rendered vars (dns_filter_groups, lan_cidr, fabric_subnet, security.firewall_allow); changed in
             place; own — fabric's own domains; shared_urls — the urls of everyone's lists.
    Returns: None.
    Fails:   ValidationError naming the group: a bad or reserved name, the same name twice; clients (see _clients),
             the same address or subnet in two groups; safe_search not true or false, youtube not strict or moderate;
             a list without an http(s) url, twice, or already on everyone; an allow or block that is not a name, is
             inside fabric's domains, or is both allowed and blocked.
    Feeds:   dns_filter/check_filter_settings."""
    groups = v.get("dns_filter_groups") or []
    if not isinstance(groups, list):
        raise ValidationError("dns_filter_groups must be a list of groups")
    security = v.get("security") or {}
    answered = []
    for c in [v.get("lan_cidr"), *(security.get("firewall_allow") or [])]:
        try:
            answered.append(ipaddress.ip_network(str(c), strict=False))
        except ValueError:
            continue
    fabric = [LOOPBACK] + ([ipaddress.ip_network(v["fabric_subnet"], strict=False)] if v.get("fabric_subnet") else [])
    names, owner = set(), {}
    out = []
    for g in groups:
        if not isinstance(g, dict):
            raise ValidationError(f"dns_filter_groups: {g!r} is not a group")
        name = str(g.get("name") or "").strip().lower()
        if not GROUP_RE.match(name) or name == "everyone":
            raise ValidationError(f"group name {name!r}: lowercase letters, digits and '-', at most 32, not "
                                  "'everyone'")
        if name in names:
            raise ValidationError(f"group {name} is there twice")
        names.add(name)
        clients = _clients(g.get("clients"), name, answered, fabric)
        for c in clients:
            if c in owner:
                raise ValidationError(f"{c} is in group {owner[c]} and group {name}: an address or subnet belongs to "
                                      "one group")
            owner[c] = name
        safe = g.get("safe_search", False)
        if not isinstance(safe, bool):
            raise ValidationError(f"group {name}: safe_search is true or false")
        youtube = str(g.get("youtube") or "strict")
        if youtube not in YOUTUBE:
            raise ValidationError(f"group {name}: youtube is strict or moderate, not {youtube!r}")
        lists, seen = [], set()
        for item in g.get("lists") or []:
            url = str((item or {}).get("url") or "").strip() if isinstance(item, dict) else ""
            if not url.startswith(("https://", "http://")):
                raise ValidationError(f"group {name}: the list {item!r} needs an http(s) url")
            if url in seen:
                raise ValidationError(f"group {name}: the list {url} is there twice")
            if url in shared_urls:
                raise ValidationError(f"group {name}: the list {url} is already on everyone, so it applies to the "
                                      "group too")
            seen.add(url)
            lists.append({"name": str(item.get("name") or url).strip(), "url": url})
        allow = rule_names(g.get("allow"), f"group {name}: allow", own)
        block = rule_names(g.get("block"), f"group {name}: block", own)
        for n in allow:                 # a group's allow is a forward zone: above fabric's zones it would hide them
            if n == "arpa" or n.endswith(".arpa") or any(d.endswith("." + n) for d in own):
                raise ValidationError(f"group {name}: allow {n} would contain fabric's own zones; allow the names "
                                      "below it instead")
        both = set(allow) & set(block)
        if both:
            raise ValidationError(f"group {name}: allowed and blocked at once: {', '.join(sorted(both))}")
        out.append({"name": name, "clients": clients, "safe_search": safe, "youtube": youtube, "lists": lists,
                    "allow": allow, "block": block})
    v["dns_filter_groups"] = out
