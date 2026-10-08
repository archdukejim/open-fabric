def plan_trust(v):
    """Purpose: adding fabric's CA to the host's trust store (manual 1.2.9.3 `trust`).
    Inputs:  v — vars: domain_file (the trust files' prefix).
    Returns: list of str (one entry: the files and update-ca-certificates).
    Fails:   never.
    Feeds:   consent/plan_host_changes, setup/init_pki."""
    prefix = f"fabric-{v.get('domain_file') or '<domain>'}"
    return [f"trust fabric's root and intermediate CA on this host: /usr/local/share/ca-certificates/{prefix}-*.crt, "
            "update-ca-certificates"]
