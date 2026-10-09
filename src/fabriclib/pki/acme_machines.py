PREFIX = "acme-"


def acme_machines(v):
    """Purpose: the LAN machines enrolled for ACME's DNS-01 (2.1.5.8): fabric's TSIG keys named acme-<name>, each
             allowed only its machine's _acme-challenge TXT record.
    Inputs:  v — settings (tsig_keys, domain).
    Returns: list of {"name", "fqdn", "key", "records"}, in the settings' order.
    Fails:   never.
    Feeds:   pki/run_acme_command (`fabricctl acme list`), agent route GET /v1/pki/acme."""
    return [{"name": k["name"][len(PREFIX):], "fqdn": f"{k['name'][len(PREFIX):]}.{v.get('domain', '')}",
             "key": k["name"], "records": list(k.get("records") or [])}
            for k in v.get("tsig_keys") or [] if k.get("name", "").startswith(PREFIX)]
