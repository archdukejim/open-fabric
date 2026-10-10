def all_lists(v):
    """Purpose: every list the DNS filter uses (manual 1.12.2.15): everyone's, then each group's own, once each.
    Inputs:  v — fabric vars (dns_filter_lists, dns_filter_groups).
    Returns: list of {"name", "url"}, in that order, each url once.
    Fails:   never (a malformed entry without a url is left out: the settings check refuses it before an apply).
    Feeds:   dns_filter/update_lists (what is fetched), dns_filter/deploy_resolver (what is kept), dns_filter/
             refresh_lists."""
    out, seen = [], set()
    items = list(v.get("dns_filter_lists") or [])
    for g in v.get("dns_filter_groups") or []:
        items += (g or {}).get("lists") or []
    for item in items:
        url = str((item or {}).get("url") or "").strip() if isinstance(item, dict) else ""
        if url and url not in seen:
            seen.add(url)
            out.append({"name": item.get("name") or url, "url": url})
    return out
