from fabriclib.security.firewall_rules import firewall_rules


def plan_ports(v, config_dir):
    """Purpose: the ports fabric itself needs opened in ufw (manual 2.7.1.3 `ports`, D121), rule by rule: the domain
             controller's (from the LAN, fabric's containers and the federation's peers), NTP, DHCP.
    Inputs:  v — vars (security.firewall, default True; firewall_rules reads the rest); config_dir — the install's
             config folder.
    Returns: list of str; [] with security.firewall false.
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings.
    Feeds:   consent/plan_host_changes, setup/configure_firewall."""
    if not (v.get("security") or {}).get("firewall", True):
        return []
    rules = firewall_rules(v, config_dir)
    return ([f"ufw: allow {r.split('@')[2]}/{r.split('@')[0]} (the Windows domain controller) from {r.split('@')[1]}"
             for r in rules["ad"]]
            + [f"ufw: allow 123/udp (NTP) from {c}" for c in rules["ntp"]]
            + [f"ufw: allow 67/udp (DHCP) in on {i}" for i in rules["dhcp"]])
