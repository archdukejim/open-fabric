from fabriclib.security.firewall_rules import firewall_rules
from fabriclib.security.ssh_ports import ssh_ports
from fabriclib.security.ufw_active import ufw_active


def plan_firewall(v, config_dir, active=None):
    """Purpose: securing the host (manual 1.2.9.3 `firewall`, 2.1.2.13), rule by rule, asked after the ports fabric
             needs (plan_ports) are allowed: incoming denied by default, ufw on, SSH from the LAN, Docker-published
             ports LAN-only — with the ports, the host is open to what fabric needs plus SSH. A new rule after a
             settings change is a new question.
    Inputs:  v — vars (security.firewall, default True; firewall_rules reads the rest); config_dir — the install's
             config folder; active — whether ufw was on before fabric (None: ufw_active, the record first), which
             only changes the first line's wording.
    Returns: list of str; [] with security.firewall false (fabric then only turns its own parts off).
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings.
    Feeds:   consent/plan_host_changes, setup/configure_firewall."""
    if not (v.get("security") or {}).get("firewall", True):
        return []
    rules = firewall_rules(v, config_dir)
    ports = ssh_ports()
    active = ufw_active(config_dir) if active is None else active
    first = ("ufw is on already: deny incoming and allow outgoing by default (the host's own rules are the next "
             "question)" if active else
             "ufw: deny incoming and allow outgoing by default, then enable ufw (existing rules are the next question)")
    return ([first]
            + [f"ufw: allow {p}/tcp (SSH) from {c}" for c in rules["ssh"] for p in ports]
            + ["iptables DOCKER-USER: ports Docker publishes are reachable only from " + ", ".join(rules["ssh"])
               + " (fabric-firewall.service re-applies this at boot)"])
