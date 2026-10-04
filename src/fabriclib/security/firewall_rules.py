import os

from fabriclib.ntp.chrony_settings import chrony_settings


def firewall_rules(v, config_dir):
    """Purpose: the networks and interfaces fabric's host firewall opens, computed once for the setup step and for
             the consent question that asks before it (manual 2.7.1).
    Inputs:  v — vars: lan_cidr, security.firewall_allow (extra CIDRs), ntp_serve (default True; chrony_settings
             decides its networks), install_kea + dhcp.interfaces; config_dir — the install's config folder
             (federation.yaml, for chrony's networks).
    Returns: {"ssh": [CIDR, ...] (22/tcp; also where Docker-published ports may be reached from), "ntp": [CIDR, ...]
             (123/udp), "dhcp": [interface, ...] (67/udp)}.
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings for invalid NTP settings.
    Feeds:   setup/configure_firewall, consent/plan_firewall."""
    security = v.get("security") or {}
    ntp = chrony_settings(v, os.path.join(config_dir, "federation.yaml"))["allow"] if v.get("ntp_serve", True) else []
    dhcp = list((v.get("dhcp") or {}).get("interfaces") or []) if v.get("install_kea") else []
    return {"ssh": [v["lan_cidr"]] + list(security.get("firewall_allow") or []), "ntp": list(ntp), "dhcp": dhcp}
