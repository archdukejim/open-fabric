def plan_resolver(v):
    """Purpose: what fabric changes in the host's resolver, only when use_host_dns is false (manual 2.7.1.3 `resolver`): BIND then needs port 53, which systemd-resolved's stub listener holds.
    Inputs:  v — vars: use_host_dns (default True), dns_server (default 8.8.8.8).
    Returns: list of str; [] with use_host_dns.
    Fails:   never.
    Feeds:   consent/plan_host_changes, setup/configure_network."""
    if v.get("use_host_dns", True):
        return []
    return [f"systemd-resolved: stub listener off and DNS={v.get('dns_server', '8.8.8.8')} "
            "(/etc/systemd/resolved.conf.d/fabric-dns.conf); /etc/resolv.conf linked to "
            "/run/systemd/resolve/resolv.conf; systemd-resolved restarted"]
