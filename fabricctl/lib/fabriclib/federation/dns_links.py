import ipaddress

from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.constants import DOMAIN_RE

ALGORITHM = "hmac-sha256"


def _link(name, record, secret):
    """Purpose: one DNS link to another site, as the BIND templates use it.
    Inputs:  name — the TSIG key name; record — {domain, address}; secret — the key's secret (or None).
    Returns: dict {key, algorithm, secret, domain, address} or None when the record or secret is unusable.
    Fails:   never.
    Feeds:   dns_links."""
    domain, address = str(record.get("domain") or ""), str(record.get("address") or "")
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return None
    if not secret or not DOMAIN_RE.match(domain):
        return None
    return {"key": name, "algorithm": ALGORITHM, "secret": secret, "domain": domain, "address": address}


def dns_links(v, secrets, registry_path):
    """Purpose: the DNS links between this site and the sites next to it in the federation (design
             federation.md M4): what BIND delegates, transfers and keeps a secondary copy of.
    Inputs:  v — fabric vars: domain; secrets — fabric's secrets (federation_tsig: {site: secret} for each site
             that joined here, "upstream": secret for this site's own upstream); registry_path — the
             federation registry (config/federation.yaml of the install being rendered).
    Returns: {"children": [link + {"site", "delegate": bool, "label"}] for each site that joined here — delegated
             when its domain is below this site's (label: the part before .<domain>) —, "upstream": link + {"site"}
             or None}. A link is {key "fed-<site>", algorithm, secret, domain, address}; sites without a usable
             address, domain or key are left out (e.g. a site that joined before M4, until it joins again).
    Fails:   yaml/OSError from load_registry.
    Feeds:   deploy.py apply_deployment (the bind9 templates: named.conf.zones, named.conf.keys, zone.j2)."""
    registry = load_registry(registry_path)
    keys = (secrets or {}).get("federation_tsig") or {}
    domain = str(v.get("domain") or "")
    children = []
    for site, record in sorted(registry["sites"].items()):
        link = _link(f"fed-{site}", record, keys.get(site))
        if link:
            below = link["domain"].endswith("." + domain)
            children.append({**link, "site": site, "delegate": below,
                             "label": link["domain"][:-(len(domain) + 1)] if below else ""})
    upstream = None
    up = registry["upstream"]
    if up:
        link = _link(up.get("dns_key") or f"fed-{up.get('site')}", up, keys.get("upstream"))
        if link:
            upstream = {**link, "site": up.get("site_name")}
    return {"children": children, "upstream": upstream}
