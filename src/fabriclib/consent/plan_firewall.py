from fabriclib.security.firewall_rules import firewall_rules


def plan_firewall(v, config_dir):
    """Purpose: the host firewall changes, rule by rule (manual 2.7.1.3 `firewall`): a new rule after a
             settings change is a new question.
    Inputs:  v — vars (security.firewall, default True; firewall_rules reads the rest); config_dir — the install's
             config folder.
    Returns: list of str; [] with security.firewall false (fabric then only turns its own parts off).
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings.
    Feeds:   consent/plan_host_changes, setup/configure_firewall."""
    if not (v.get("security") or {}).get("firewall", True):
        return []
    rules = firewall_rules(v, config_dir)
    return (["ufw: deny incoming and allow outgoing by default, then enable ufw (existing rules are kept)"]
            + [f"ufw: allow 22/tcp (SSH) from {c}" for c in rules["ssh"]]
            + [f"ufw: allow 123/udp (NTP) from {c}" for c in rules["ntp"]]
            + [f"ufw: allow 67/udp (DHCP) in on {i}" for i in rules["dhcp"]]
            + ["iptables DOCKER-USER: ports Docker publishes are reachable only from " + ", ".join(rules["ssh"])
               + " (fabric-firewall.service re-applies this at boot)"])
