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


def _rules(allowed_cidrs):
    rules = [["-m", "conntrack", "--ctstate", "RELATED,ESTABLISHED", "-j", "RETURN"],
             # traffic originating from containers (fabric_net or any other bridge)
             ["-i", "docker0", "-j", "RETURN"],
             ["-i", "br-+", "-j", "RETURN"]]
    rules += [["-s", cidr, "-j", "RETURN"] for cidr in allowed_cidrs]
    rules.append(["-m", "conntrack", "--ctstate", "NEW", "-j", "DROP"])
    return rules


def apply_docker_firewall(vars_file):
    """Flush and rebuild DOCKER-USER: only the LAN (and security.firewall_allow)
    may open new connections to published container ports."""
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
    for rule in _rules(allowed):
        subprocess.run(["iptables", "-A", "DOCKER-USER", *rule], check=True)
    return f"published ports limited to {', '.join(allowed)}"


if __name__ == "__main__":
    print(apply_docker_firewall(sys.argv[1]))
