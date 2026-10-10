import ipaddress
import json
import subprocess


def host_networks():
    """Purpose: this host's IPv4 addresses by interface, as `ip` reports them: what DHCP's subnets are placed on
             (manual 1.10.3.2).
    Inputs:  none (runs `ip -j -4 addr`).
    Returns: {interface name: [ipaddress.IPv4Interface, ...]}; {} when `ip` is missing or fails (not a Linux host).
    Fails:   never.
    Feeds:   dhcp/place_subnets (through deploy/check_settings)."""
    try:
        out = subprocess.run(["ip", "-j", "-4", "addr"], capture_output=True, text=True, check=True).stdout
        links = json.loads(out or "[]")
    except (OSError, subprocess.CalledProcessError, ValueError):
        return {}
    nets = {}
    for link in links:
        for a in link.get("addr_info") or []:
            if a.get("family") == "inet" and a.get("local"):
                nets.setdefault(link["ifname"], []).append(ipaddress.ip_interface(f"{a['local']}/{a['prefixlen']}"))
    return nets
