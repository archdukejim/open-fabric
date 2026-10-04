"""Filter traffic to Docker-published ports (DOCKER-USER chain).

UFW cannot do this: Docker routes published ports through its own
iptables chains before UFW's INPUT rules ever see them. DOCKER-USER is the
chain Docker reserves for exactly this; fabric owns its contents.

Run by `fabricctl setup` and at every boot by fabric-firewall.service:
    python3 -m fabriclib.security.apply_docker_firewall <vars.yaml>
"""
import subprocess
import sys

import yaml


def _rules(allowed_cidrs, radius_sources=()):
    """Purpose: the DOCKER-USER rules, in order.
    Inputs:  allowed_cidrs — sources that may open connections; radius_sources — RADIUS client addresses
             (allowed to UDP 1812/1813 only; default none).
    Returns: list of iptables rule argument lists: established traffic, traffic from docker0 and br-* bridges,
             each allowed CIDR and RADIUS source return; any other NEW connection is dropped.
    Fails:   never.
    Feeds:   apply_docker_firewall."""
    rules = [["-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "RETURN"],
             # traffic originating from containers (fabric_net or any other bridge)
             ["-i", "docker0", "-j", "RETURN"],
             ["-i", "br-+", "-j", "RETURN"]]
    rules += [["-s", cidr, "-j", "RETURN"] for cidr in allowed_cidrs]
    # RADIUS clients (switches, APs) may sit outside the LAN: RADIUS ports only
    rules += [["-s", src, "-p", "udp", "-m", "multiport", "--dports", "1812,1813", "-j", "RETURN"]
              for src in radius_sources]
    rules.append(["-m", "conntrack", "--ctstate", "NEW", "-j", "DROP"])
    return rules


def apply_docker_firewall(vars_file):
    """Purpose: flush and rebuild DOCKER-USER so only the LAN (and security.firewall_allow) may open new
             connections to Docker-published ports, and RADIUS clients (802.1X) only to FreeRADIUS's ports.
    Inputs:  vars_file — rendered vars.yaml: lan_cidr, security.firewall (default True),
             security.firewall_allow, install_freeradius, radius_clients (IPv4 addresses; IPv6 skipped).
    Returns: a summary str: "published ports limited to <cidrs>", or "disabled" when security.firewall is false
             (chain flushed to a single RETURN).
    Fails:   OSError/yaml errors reading vars_file; KeyError without lan_cidr; CalledProcessError from iptables.
    Feeds:   configure_firewall.run (setup) and fabric-firewall.service at boot (`python3 -m ...`, prints it).
    Notes:   UFW cannot filter these ports: Docker routes them through its own chains before INPUT."""
    with open(vars_file) as f:
        v = yaml.safe_load(f) or {}
    security = v.get("security") or {}
    if not security.get("firewall", True):
        subprocess.run(["iptables", "-F", "DOCKER-USER"], capture_output=True)
        subprocess.run(["iptables", "-A", "DOCKER-USER", "-j", "RETURN"], capture_output=True)
        return "disabled"
    allowed = [v["lan_cidr"]] + list(security.get("firewall_allow") or [])
    if subprocess.run(["iptables", "-L", "DOCKER-USER", "-n"], capture_output=True).returncode != 0:
        subprocess.run(["iptables", "-N", "DOCKER-USER"], check=True)
    subprocess.run(["iptables", "-F", "DOCKER-USER"], check=True)
    radius = [c["address"] for c in v.get("radius_clients") or []
              if v.get("install_freeradius") and ":" not in str(c.get("address", ""))]
    for rule in _rules(allowed, radius):
        subprocess.run(["iptables", "-A", "DOCKER-USER", *rule], check=True)
    return f"published ports limited to {', '.join(allowed)}"


if __name__ == "__main__":
    print(apply_docker_firewall(sys.argv[1]))
