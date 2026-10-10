import ipaddress
import re

from fabriclib.dns_filter.common.list_zone import list_zone
from fabriclib.dns_filter.common.safe_search import ZONES as SAFE_ZONES

BASE_MB = 16                     # the resolver itself, its cache and fabric's own zones (2.3.12.1.17: 9 MiB measured)
HEADROOM = 0.8                   # lists may take the estimate to 80% of the memory limit, never further (2.3.12.1.25)


def _limit_mb(value):
    """Purpose: a Docker memory limit as MiB.
    Inputs:  value — "384m", "1g", "402653184" (bytes) or None.
    Returns: float, or None when there is no limit or it does not parse.
    Fails:   never.
    Feeds:   resolver_views."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*([kmg]?)b?\s*$", str(value or "").lower())
    if not m:
        return None
    n = float(m.group(1))
    return {"": n / 1048576, "k": n / 1024, "m": n, "g": n * 1024}[m.group(2)]


def _matches(groups):
    """Purpose: each group's match-clients, so that the most specific address wins and no two groups match one
             client: before each of a group's entries, the other groups' more specific entries inside it, negated.
    Inputs:  groups — the checked groups (check_filter_groups: clients normalised, never the same entry twice).
    Returns: {group name: [address-match-list elements, in order]}.
    Fails:   never.
    Feeds:   resolver_views."""
    entries = [(g["name"], ipaddress.ip_network(c)) for g in groups for c in g["clients"]]
    out = {}
    for g in groups:
        elems = []
        for c in g["clients"]:
            net = ipaddress.ip_network(c)
            inner = sorted((n for owner, n in entries if owner != g["name"] and n != net and n.subnet_of(net)),
                           key=lambda n: (-n.prefixlen, int(n.network_address)))
            elems += ["!" + (str(n.network_address) if n.prefixlen == 32 else str(n)) for n in inner]
            elems.append(c)
        out[g["name"]] = list(dict.fromkeys(elems))
    return out


def resolver_views(v, present, state):
    """Purpose: what the resolver's views load (manual 1.12.2.15): everyone's lists, then each group's view (its
             match-clients, its rules zone, its safe search, its own lists, its allowed names); each list counted
             against the memory limit in that order and left out when its copy would pass 80% of it.
    Inputs:  v — checked vars (dns_filter_lists, dns_filter_groups, dns_filter_safe_search, dns_filter_youtube,
             resolver_mem_limit); present — set of list zones that have a converted copy; state — the lists' state
             (update_lists: {zone: {memory_mb, ...}}).
    Returns: {"lists": [{zone, name}] for everyone, "safe_zone": everyone's safe-search zone or None, "groups":
             [{name, match, rules_zone, safe_zone, lists, allow}], "memory": {"estimate_mb", "limit_mb",
             "left_out": [{view, zone, name}]}}.
    Fails:   never.
    Feeds:   dns_filter/deploy_resolver."""
    limit = _limit_mb(v.get("resolver_mem_limit"))
    budget = limit * HEADROOM if limit else None
    used = float(BASE_MB)
    left_out = []

    def place(view, items):
        nonlocal used
        kept = []
        for item in items:
            zone = list_zone(item["url"])
            if zone not in present:
                continue
            mb = float((state.get(zone) or {}).get("memory_mb") or 0)
            if budget is not None and used + mb > budget:
                left_out.append({"view": view, "zone": zone, "name": item.get("name") or item["url"]})
                continue
            used += mb
            kept.append({"zone": zone, "name": item.get("name") or item["url"]})
        return kept

    lists = place("everyone", v.get("dns_filter_lists") or [])
    matches = _matches(v.get("dns_filter_groups") or [])
    groups = []
    for g in v.get("dns_filter_groups") or []:
        groups.append({"name": g["name"], "match": matches[g["name"]], "rules_zone": f"group-{g['name']}.rpz",
                       "safe_zone": SAFE_ZONES[g["youtube"]] if g["safe_search"] else None,
                       "lists": place(g["name"], g["lists"]), "allow": g["allow"]})
    safe = SAFE_ZONES[v.get("dns_filter_youtube") or "strict"] if v.get("dns_filter_safe_search") else None
    return {"lists": lists, "safe_zone": safe, "groups": groups,
            "memory": {"estimate_mb": round(used, 1), "limit_mb": round(limit, 1) if limit else None,
                       "left_out": left_out}}
