from fabriclib.federation.common.load_registry import load_registry

LDAPS_PORT = 636


def _account(site):
    """Purpose: the name of the bind account a site's supplier uses at a neighbour (cn=<it>,cn=config).
    Inputs:  site — the pushing site's name.
    Returns: str "repl-from-<site>".
    Fails:   never.
    Feeds:   directory_links."""
    return f"repl-from-{site}"


def directory_links(v, secrets, registry_path):
    """Purpose: what this site's 389-DS replicates, as replicas and agreements (design federation.md §3.2a): the
             organisation comes down from the upstream (supplied here at the root), this site's part goes up, the
             parts of the sites that joined here are kept as copies.
    Inputs:  v — fabric vars: site_name, ldap_base_dn, ldap_local_dn (this site's part); secrets — fabric's
             secrets (federation_replication: {site: secret} for each site that joined here, "upstream": the
             secret with this site's upstream); registry_path — config/federation.yaml.
    Returns: {"replicas": [{"suffix", "role", "replica_id", "accounts": {name: secret}, "referral"}],
             "agreements": [{"suffix", "name", "host", "port", "bind_dn", "secret", "description"}],
             "backends": [{"suffix", "name"}] — copies of joined sites' parts to create here}; all empty on a
             standalone install (no upstream, no sites). Links without a
             secret or an LDAP name (sites that joined before M5, until they join again) are left out.
    Fails:   yaml/OSError from load_registry.
    Feeds:   configure_directory_links; tests/federation/directory_links.py.
    Notes:   at a site the organisation is a read-only copy (a consumer, or a hub when sites joined below it)
             that refers writes to the upstream; only one site writes each suffix, so every supplier is replica
             id 1. A joined site's part is a consumer here (it reaches the root when this is the root; parts of
             sites nested further down reach only their parent for now)."""
    registry = load_registry(registry_path)
    keys = (secrets or {}).get("federation_replication") or {}
    me, base, part = v["site_name"], v["ldap_base_dn"], v["ldap_local_dn"]
    up = registry.get("upstream") or {}
    children = {s: r for s, r in sorted(registry["sites"].items()) if keys.get(s) and r.get("ldap_host")}
    up_ok = bool(up and keys.get("upstream") and up.get("ldap_host") and up.get("site_name"))
    replicas, agreements, backends = [], [], []
    if not up and not registry["sites"]:            # standalone: nothing replicates (no changelog either)
        return {"replicas": replicas, "agreements": agreements, "backends": backends}

    if not up:
        replicas.append({"suffix": base, "role": "supplier", "replica_id": 1, "accounts": {}, "referral": None})
    elif up_ok:
        upstream_url = f"ldaps://{up['ldap_host']}:{int(up.get('ldap_port') or LDAPS_PORT)}"
        replicas.append({"suffix": base, "role": "hub" if children else "consumer", "replica_id": 0,
                         "accounts": {_account(up["site_name"]): keys["upstream"]}, "referral": upstream_url})
    replicas.append({"suffix": part, "role": "supplier", "replica_id": 1, "accounts": {}, "referral": None})
    if up_ok:
        agreements.append({"suffix": part, "name": f"to-{up['site_name']}", "host": up["ldap_host"],
                           "port": int(up.get("ldap_port") or LDAPS_PORT), "bind_dn": f"cn={_account(me)},cn=config",
                           "secret": keys["upstream"], "description": f"{me}'s part to its parent {up['site_name']}"})
    for site, rec in children.items():
        child_part = f"ou={site},{base}"
        backends.append({"suffix": child_part, "name": f"part_{site}".replace("-", "_")})
        port = int(rec.get("ldap_port") or LDAPS_PORT)
        replicas.append({"suffix": child_part, "role": "consumer", "replica_id": 0,
                         "accounts": {_account(site): keys[site]}, "referral": f"ldaps://{rec['ldap_host']}:{port}"})
        agreements.append({"suffix": base, "name": f"to-{site}", "host": rec["ldap_host"], "port": port,
                           "bind_dn": f"cn={_account(me)},cn=config", "secret": keys[site],
                           "description": f"the organisation to {site}"})
    return {"replicas": replicas, "agreements": agreements, "backends": backends}
