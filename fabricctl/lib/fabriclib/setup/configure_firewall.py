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
    """Purpose: the IP address the current SSH session comes from.
    Inputs:  none (env SSH_CONNECTION; sudo must keep it).
    Returns: the client address (str), or None when not over SSH.
    Fails:   never.
    Feeds:   run (lockout guard)."""
    parts = os.environ.get("SSH_CONNECTION", "").split()
    return parts[0] if parts else None


def run(ctx):
    """Purpose: default-deny host firewall (UFW: SSH from the LAN only) plus DOCKER-USER rules so
             Docker-published ports are LAN-only too, re-applied at boot by fabric-firewall.service.
    Inputs:  ctx — SetupContext: vars lan_cidr, security.firewall (default True), security.firewall_allow
             (extra CIDRs, e.g. a VPN), install_kea + dhcp.interfaces (UDP 67 allowed on them); vars_file,
             target_dir, config_dir. Env SSH_CONNECTION.
    Returns: None. On: ufw defaults deny in/allow out, SSH (22/tcp) from each allowed CIDR, ufw enabled
             (existing ufw rules kept; SSH rules fabric added earlier for a CIDR no longer allowed are removed —
             config/.firewall-ssh-allowed records fabric's own), UNIT written, enabled and restarted, DOCKER-USER
             rebuilt. Off: DOCKER-USER
             opened (apply_docker_firewall returns "disabled"), fabric-firewall disabled, a warning; ufw is left
             as it is.
    Fails:   SetupError when the SSH client is outside every allowed CIDR (would lock the operator out);
             CalledProcessError from ufw, systemctl or iptables; KeyError without lan_cidr; ValueError for an
             invalid CIDR.
    Feeds:   setup step `firewall`, run by run_setup via STEPS."""
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
    # SSH rules fabric added for a network that is no longer allowed (lan_cidr changed, a firewall_allow entry
    # removed) go; rules fabric did not add are never touched. The record says which are fabric's.
    record = os.path.join(ctx.config_dir, ".firewall-ssh-allowed")
    previous = open(record).read().split() if os.path.exists(record) else []
    for cidr in previous:
        if cidr not in allowed:
            subprocess.run(["ufw", "delete", "allow", "from", cidr, "to", "any", "port", "22", "proto", "tcp"],
                           capture_output=True)
            info(f"host firewall: SSH from {cidr} removed (no longer allowed)")
    with open(record, "w") as f:
        f.write("\n".join(allowed) + "\n")
    # DHCP (optional): clients have no address yet (source 0.0.0.0), so allow port 67 on the served interfaces
    if ctx.vars.get("install_kea"):
        for iface in (ctx.vars.get("dhcp") or {}).get("interfaces") or []:
            subprocess.run(["ufw", "allow", "in", "on", iface, "to", "any", "port", "67", "proto", "udp"],
                           check=True, capture_output=True)
    subprocess.run(["ufw", "--force", "enable"], check=True, capture_output=True)

    lib = os.path.join(ctx.target_dir, "lib")
    with open(UNIT, "w") as f:
        f.write(UNIT_TEXT.format(lib=lib, vars=ctx.vars_file))
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "fabric-firewall"], check=True, capture_output=True)
    subprocess.run(["systemctl", "restart", "fabric-firewall"], check=True)
    ok(apply_docker_firewall(ctx.vars_file) + " (re-applied at boot by fabric-firewall.service)")
