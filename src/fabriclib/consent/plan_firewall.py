from fabriclib.security.firewall_rules import firewall_rules
from fabriclib.security.ssh_ports import ssh_ports
from fabriclib.security.ufw_active import ufw_active


def plan_firewall(v, config_dir, active=None):
    """Purpose: the host firewall changes, rule by rule (manual 2.7.1.3 `firewall`): a new rule after a
             settings change is a new question.
    Inputs:  v — vars (security.firewall, default True; firewall_rules reads the rest); config_dir — the install's
             config folder; active — whether ufw is on already (None: ask ufw). With ufw on (D119), the question says
             the host's own rules stay and lists the ports fabric opens beside them, instead of turning ufw on.
    Returns: list of str; [] with security.firewall false (fabric then only turns its own parts off).
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings.
    Feeds:   consent/plan_host_changes, setup/configure_firewall."""
    if not (v.get("security") or {}).get("firewall", True):
        return []
    rules = firewall_rules(v, config_dir)
    ports = ssh_ports()
    active = ufw_active(config_dir) if active is None else active
    first = ("ufw is on already, with your own rules: they stay; fabric only opens the ports below beside them"
             if active else
             "ufw: deny incoming and allow outgoing by default, then enable ufw (existing rules are kept)")
    return ([first]
            + [f"ufw: allow {p}/tcp (SSH) from {c}" for c in rules["ssh"] for p in ports]
            + [f"ufw: allow 123/udp (NTP) from {c}" for c in rules["ntp"]]
            + [f"ufw: allow 67/udp (DHCP) in on {i}" for i in rules["dhcp"]]
            + [f"ufw: allow {r.split('@')[2]}/{r.split('@')[0]} (the Windows domain controller) from {r.split('@')[1]}"
               for r in rules["ad"]]
            + ["iptables DOCKER-USER: ports Docker publishes are reachable only from " + ", ".join(rules["ssh"])
               + " (fabric-firewall.service re-applies this at boot)"])
