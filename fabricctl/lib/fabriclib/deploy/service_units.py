def service_units(base, v):
    """Purpose: fabric's container services, each run by a systemd wrapper unit around its compose file.
    Inputs:  base — the deploy base (/opt); v — rendered settings (install_* flags).
    Returns: [{"service" (unit), "compose" (the container its health check waits on), "folder" (<base>/<folder>,
             jinja/<folder>), "requires" (units), optional "condition", "post", "enabled" (bool: installed on this
             host)}], in a fixed order.
    Fails:   never.
    Feeds:   render_templates (compose files and wrappers of the enabled ones), install_service_units;
             tests/render.py (every unit's container must be in its compose file)."""
    cli = f"/usr/bin/python3 {base}/fabric/lib/fabriclib/cli.py"
    units = [
        {'service': 'nginx', 'compose': 'nginx', 'folder': 'nginx', 'requires': []},
        {'service': 'bind9', 'compose': 'bind9', 'folder': 'bind9', 'requires': []},
        {'service': 'stepca', 'compose': 'step-ca', 'folder': 'stepca', 'requires': []},
        {'service': 'ldap', 'compose': 'dirsrv', 'folder': 'dirsrv', 'requires': []},
        {'service': 'postgres', 'compose': 'postgres', 'folder': 'postgres', 'requires': []},
        {'service': 'keycloak', 'compose': 'keycloak', 'folder': 'keycloak', 'requires': ['postgres']},
        {'service': 'fabric-web', 'compose': 'fabric-web', 'folder': 'webui', 'requires': ['fabric-agent']},
        # fabric-unlock: OpenBao starts only when an unlock method gives its key; the key is wiped once unsealed.
        {'service': 'openbao', 'compose': 'openbao', 'folder': 'openbao', 'requires': [],
         'condition': f"{cli} vault unlock", 'post': [f"{cli} vault wipe-key"]},
        # optional log forwarding (design D20)
        {'service': 'fluentbit', 'compose': 'fluentbit', 'folder': 'fluentbit', 'requires': []},
        # optional DHCP (design §5): kea-dhcp4 on the host network + kea-ddns
        {'service': 'kea', 'compose': 'kea-dhcp4', 'folder': 'kea', 'requires': ['bind9']},
        # optional 802.1X (design §6): asks 389-DS about every device
        {'service': 'freeradius', 'compose': 'freeradius', 'folder': 'freeradius', 'requires': ['ldap']},
        # optional DNS filter (manual 2.4.1): AdGuard Home on host_ip:53 in front of BIND, oauth2-proxy for its UI;
        # no requires: a BIND restart (every DNS apply) must not take the clients' DNS down with it
        {'service': 'adguard', 'compose': 'adguardhome', 'folder': 'adguard', 'requires': []},
        # its sign-in, a unit of its own: when it or Keycloak is down only AdGuard's UI is, never DNS
        {'service': 'adguard-auth', 'compose': 'oauth2-proxy-adguard', 'folder': 'adguard-auth', 'requires': []},
    ]
    flag = {"keycloak": "install_keycloak", "postgres": "install_keycloak", "dirsrv": "install_ldap",
            "webui": "install_webui", "fluentbit": "install_fluentbit", "kea": "install_kea",
            "freeradius": "install_freeradius", "adguard": "install_adguard", "adguard-auth": "install_adguard"}
    for u in units:
        u["enabled"] = bool(v.get(flag[u["folder"]])) if u["folder"] in flag else True
    return units
