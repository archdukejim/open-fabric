import os

from fabriclib.federation.common.load_registry import load_registry
from fabriclib.ntp.chrony_settings import chrony_settings

# the domain controller's ports (manual 2.11.2.4), besides 53 (BIND, published by Docker): Kerberos, the RPC endpoint
# mapper, LDAP (CLDAP on UDP), SMB, kpasswd, LDAPS, the global catalog, then its RPC range
AD_TCP = "88,135,389,445,464,636,3268,3269"
AD_UDP = "88,389,464"


def firewall_rules(v, config_dir):
    """Purpose: the networks and interfaces fabric's host firewall opens, computed once for the setup step and for
             the consent question that asks before it (manual 2.7.1).
    Inputs:  v — vars: lan_cidr, security.firewall_allow (extra CIDRs), ntp_serve (default True; chrony_settings
             decides its networks), install_kea + dhcp.interfaces; config_dir — the install's config folder
             (federation.yaml, for chrony's networks and the federation's peers); ad_rpc_ports + fabric_subnet
             (the DC).
    Returns: {"ssh": [CIDR, ...] (SSH, on the ports sshd listens on; also where Docker-published ports may be
             reached from), "ntp": [CIDR, ...]
             (123/udp), "dhcp": [interface, ...] (67/udp), "ad": ["<proto>@<CIDR>@<ports>", ...] (the domain
             controller's ports, from the SSH networks, fabric's container subnet and the federation's peers: the
             upstream's and every joined site's address)}.
    Fails:   KeyError without lan_cidr; ValidationError from chrony_settings for invalid NTP settings.
    Feeds:   setup/configure_firewall, consent/plan_firewall."""
    security = v.get("security") or {}
    ntp = chrony_settings(v, os.path.join(config_dir, "federation.yaml"))["allow"] if v.get("ntp_serve", True) else []
    dhcp = list((v.get("dhcp") or {}).get("interfaces") or []) if v.get("install_kea") else []
    ssh = [v["lan_cidr"]] + list(security.get("firewall_allow") or [])
    ad = []
    rpc = str(v.get("ad_rpc_ports") or "49152-49251").replace("-", ":")
    # Keycloak and FreeRADIUS reach the DC at the host's address from fabric_net; the DCs of the sites next to this
    # one replicate with it (manual 1.8.8.5): its upstream's and each joined site's address
    registry = load_registry(os.path.join(config_dir, "federation.yaml"))
    peers = [p["address"] for p in [registry.get("upstream") or {}, *registry.get("sites", {}).values()]
             if p.get("address")]
    peers = [f"{a}/{128 if ':' in a else 32}" for a in peers]
    for cidr in ssh + [v["fabric_subnet"]] + [p for p in peers if p not in ssh]:
        ad += [f"tcp@{cidr}@{AD_TCP},{rpc}", f"udp@{cidr}@{AD_UDP}"]
    return {"ssh": ssh, "ntp": list(ntp), "dhcp": dhcp, "ad": ad}
