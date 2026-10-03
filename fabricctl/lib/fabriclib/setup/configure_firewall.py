import ipaddress
import os
import subprocess

from fabriclib.common.console import info, ok, warn
from fabriclib.common.keep_original import ORIGINALS
from fabriclib.consent.check_consent import check_consent
from fabriclib.consent.plan_firewall import plan_firewall
from fabriclib.security.apply_docker_firewall import apply_docker_firewall
from fabriclib.security.firewall_rules import firewall_rules
from fabriclib.security.ufw_rule import RECORDS, ufw_rule
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


def _forget_rules(config_dir, kind, allowed, what):
    """Purpose: remove the ufw rules fabric added earlier for networks or interfaces no longer allowed; record the
             current ones.
    Inputs:  config_dir — the install's config folder (security/ufw_rule RECORDS: what fabric opened last time);
             kind — "ssh", "ntp" or "dhcp"; allowed — the networks or interfaces now; what — the service's name for
             messages.
    Returns: None; the record rewritten with allowed. Rules fabric did not add are never touched.
    Fails:   OSError writing the record (a failing `ufw delete` is ignored: the rule may be gone already).
    Feeds:   run."""
    record = os.path.join(config_dir, RECORDS[kind])
    previous = open(record).read().split() if os.path.exists(record) else []
    for x in previous:
        if x not in allowed:
            subprocess.run(["ufw", "delete", "allow", *ufw_rule(kind, x)], capture_output=True)
            info(f"host firewall: {what} from {x} removed (no longer allowed)")
    with open(record, "w") as f:
        f.write("\n".join(allowed) + ("\n" if allowed else ""))


def _keep_ufw_state(config_dir):
    """Purpose: record once whether ufw was on before fabric first enabled it, so undoing the firewall can leave it
             as it was (manual 2.7.1.5).
    Inputs:  config_dir — the install's config folder (<config>/host-originals/ufw.state).
    Returns: None; the record written only when absent ("active" or "inactive").
    Fails:   OSError writing it; FileNotFoundError without ufw.
    Feeds:   run; read by undo/undo_firewall."""
    path = os.path.join(config_dir, ORIGINALS, "ufw.state")
    if os.path.exists(path):
        return
    out = subprocess.run(["ufw", "status"], capture_output=True, text=True).stdout
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    with open(path, "w") as f:
        f.write("active\n" if "Status: active" in out else "inactive\n")


def run(ctx):
    """Purpose: default-deny host firewall (UFW: SSH from the LAN only) plus DOCKER-USER rules so
             Docker-published ports are LAN-only too, re-applied at boot by fabric-firewall.service.
    Inputs:  ctx — SetupContext: vars lan_cidr, security.firewall (default True), security.firewall_allow
             (extra CIDRs, e.g. a VPN), install_kea + dhcp.interfaces (UDP 67 allowed on them), ntp_serve (UDP 123
             from the networks chrony answers — chrony_settings —, fabric's earlier NTP rules for other networks
             removed: config/.firewall-ntp-allowed; DHCP likewise) — the rules come from security/firewall_rules; vars_file,
             target_dir, config_dir. Env SSH_CONNECTION.
    Returns: None. On: ufw defaults deny in/allow out, SSH (22/tcp) from each allowed CIDR, ufw enabled
             (existing ufw rules kept; SSH rules fabric added earlier for a CIDR no longer allowed are removed —
             config/.firewall-ssh-allowed records fabric's own; whether ufw was on before is recorded once for undo), UNIT written, enabled and restarted, DOCKER-USER
             rebuilt — only after the `firewall` consent (else a warning, the host firewall left as it is).
             Off: DOCKER-USER
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

    rules = firewall_rules(ctx.vars, ctx.config_dir)
    allowed = rules["ssh"]
    client = _ssh_client()
    if client and not any(ipaddress.ip_address(client) in ipaddress.ip_network(c, strict=False) for c in allowed):
        raise SetupError(f"your SSH session comes from {client}, outside {', '.join(allowed)}; enabling the "
                         f"firewall would lock you out. Add it to security.firewall_allow or connect from the LAN.")

    if not check_consent(ctx.config_dir, "firewall", plan_firewall(ctx.vars, ctx.config_dir)):
        return
    _keep_ufw_state(ctx.config_dir)
    info("host firewall (ufw): deny incoming, allow SSH from " + ", ".join(allowed))
    # Existing ufw rules are kept; fabric only sets the defaults and adds its own.
    for cmd in (["ufw", "default", "deny", "incoming"], ["ufw", "default", "allow", "outgoing"]):
        subprocess.run(cmd, check=True, capture_output=True)
    for cidr in allowed:
        subprocess.run(["ufw", "allow", *ufw_rule("ssh", cidr)], check=True, capture_output=True)
    # SSH rules fabric added for a network that is no longer allowed (lan_cidr changed, a firewall_allow entry
    # removed) go; rules fabric did not add are never touched. The record says which are fabric's.
    _forget_rules(ctx.config_dir, "ssh", allowed, "SSH")
    # time (manual 2.5.1): the networks chrony answers may ask on UDP 123, nobody else
    ntp_nets = rules["ntp"]
    for cidr in ntp_nets:
        subprocess.run(["ufw", "allow", *ufw_rule("ntp", cidr)], check=True, capture_output=True)
    _forget_rules(ctx.config_dir, "ntp", ntp_nets, "NTP")
    # DHCP (optional): clients have no address yet (source 0.0.0.0), so allow port 67 on the served interfaces
    for iface in rules["dhcp"]:
        subprocess.run(["ufw", "allow", *ufw_rule("dhcp", iface)], check=True, capture_output=True)
    _forget_rules(ctx.config_dir, "dhcp", rules["dhcp"], "DHCP")
    subprocess.run(["ufw", "--force", "enable"], check=True, capture_output=True)

    lib = os.path.join(ctx.target_dir, "lib")
    with open(UNIT, "w") as f:
        f.write(UNIT_TEXT.format(lib=lib, vars=ctx.vars_file))
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "enable", "fabric-firewall"], check=True, capture_output=True)
    subprocess.run(["systemctl", "restart", "fabric-firewall"], check=True)
    ok(apply_docker_firewall(ctx.vars_file) + " (re-applied at boot by fabric-firewall.service)")
