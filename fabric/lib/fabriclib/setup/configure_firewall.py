import ipaddress
import os
import subprocess

from fabriclib.common.console import info, ok, warn
from fabriclib.security.apply_docker_firewall import apply_docker_firewall
from fabriclib.setup.errors import SetupError

UNIT = "/etc/systemd/system/fabric-firewall.service"
UNIT_TEXT = """[Unit]
Description=fabric: limit Docker-published ports to the LAN (DOCKER-USER)
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
Environment=PYTHONPATH={lib}
ExecStart=/usr/bin/python3 -m fabriclib.security.apply_docker_firewall {vars}

[Install]
WantedBy=multi-user.target docker.service
"""


def _ssh_client():
    parts = os.environ.get("SSH_CONNECTION", "").split()
    return parts[0] if parts else None


def run(ctx):
    """Default-deny host firewall (UFW: SSH from the LAN only) plus DOCKER-USER
    rules so Docker-published ports are LAN-only too. Relax with
    security.firewall: false; add ranges (e.g. a VPN) with
    security.firewall_allow: [cidr, ...]."""
    security = ctx.vars.get("security") or {}
    if not security.get("firewall", True):
        apply_docker_firewall(ctx.vars_file)
        subprocess.run(["systemctl", "disable", "--now", "fabric-firewall"], capture_output=True)
        warn("firewall disabled (security.firewall: false): published ports are reachable from anywhere")
        return

    allowed = [ctx.vars["lan_cidr"]] + list(security.get("firewall_allow") or [])
    client = _ssh_client()
    if client and not any(ipaddress.ip_address(client) in ipaddress.ip_network(c, strict=False) for c in allowed):
        raise SetupError(f"your SSH session comes from {client}, outside {', '.join(allowed)}; enabling the "
                         f"firewall would lock you out. Add it to security.firewall_allow or connect from the LAN.")

    info("host firewall (ufw): deny incoming, allow SSH from " + ", ".join(allowed))
    # Existing ufw rules are kept; fabric only sets the defaults and adds its own.
    for cmd in (["ufw", "default", "deny", "incoming"], ["ufw", "default", "allow", "outgoing"]):
        subprocess.run(cmd, check=True, capture_output=True)
    for cidr in allowed:
        subprocess.run(["ufw", "allow", "from", cidr, "to", "any", "port", "22", "proto", "tcp"],
                       check=True, capture_output=True)
    subprocess.run(["ufw", "--force", "enable"], check=True, capture_output=True)

    lib = os.path.join(ctx.target_dir, "lib")
    with open(UNIT, "w") as f:
        f.write(UNIT_TEXT.format(lib=lib, vars=ctx.vars_file))
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "fabric-firewall"], check=True, capture_output=True)
    subprocess.run(["systemctl", "restart", "fabric-firewall"], check=True)
    ok(apply_docker_firewall(ctx.vars_file) + " (re-applied at boot by fabric-firewall.service)")
