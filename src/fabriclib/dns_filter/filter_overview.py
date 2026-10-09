import json

from fabriclib.common.errors import ValidationError
from fabriclib.dns_filter.common.list_zone import list_zone
from fabriclib.dns_filter.common.resolver_paths import resolver_paths
from fabriclib.dns_filter.dns_filter_stats import dns_filter_stats


def filter_overview(v):
    """Purpose: the DNS filter for the web console (manual 1.12.2.13; `dns:filter`): its settings that people manage,
             each list's state and the statistics (no client addresses, 2.1.12.4).
    Inputs:  v — rendered vars (dns_filter, install_resolver, dns_filter_lists, dns_filter_allow, dns_filter_block,
             dns_filter_upstreams, resolver_mem_limit, deploy_base_dir).
    Returns: {"on": bool, "lists": [{name, url, zone, last_fetch, last_success, rules, skipped, memory_mb, error}],
             "allow", "block", "upstreams", "memory_limit", "stats": dns_filter_stats' result, or {"off": reason}
             (the query log off, or Postgres refusing: its message)}.
    Fails:   never for the statistics (a refusal is reported in stats.off); OSError reading the state file other
             than its absence.
    Feeds:   agent/get_route (GET /v1/dns-filter)."""
    if not v.get("install_resolver"):
        return {"on": False, "lists": [], "allow": [], "block": [], "upstreams": [], "memory_limit": None,
                "stats": {"off": "the BIND resolver is off"}}
    try:
        with open(resolver_paths(v)["state"]) as f:
            state = json.load(f)
    except (FileNotFoundError, ValueError):
        state = {}
    lists = []
    for item in v.get("dns_filter_lists") or []:
        zone = list_zone(item["url"])
        st = state.get(zone, {})
        lists.append({"name": item.get("name") or item["url"], "url": item["url"], "zone": zone,
                      **{k: st.get(k) for k in ("last_fetch", "last_success", "rules", "skipped", "memory_mb",
                                                "error")}})
    try:
        stats = dns_filter_stats(v)
    except ValidationError as e:
        stats = {"off": str(e)}
    return {"on": True, "lists": lists, "allow": v.get("dns_filter_allow") or [],
            "block": v.get("dns_filter_block") or [], "upstreams": v.get("dns_filter_upstreams") or [],
            "memory_limit": v.get("resolver_mem_limit"), "stats": stats}
