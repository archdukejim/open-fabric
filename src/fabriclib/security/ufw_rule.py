# what fabric opened, by kind: files in the install's config folder (rules fabric did not add are never touched)
RECORDS = {"ssh": ".firewall-ssh-allowed", "ntp": ".firewall-ntp-allowed", "dhcp": ".firewall-dhcp-allowed",
           "ad": ".firewall-ad-allowed"}


def ufw_rule(kind, what):
    """Purpose: the ufw rule fabric adds for one network or interface, as the words after `ufw allow` (and after
             `ufw delete allow` to remove it).
    Inputs:  kind — "ssh" (sshd's port/tcp from a CIDR), "ntp" (123/udp from a CIDR), "dhcp" (67/udp in on an
             interface) or "ad" (the domain controller's ports); what — the CIDR ("ssh": "<CIDR>@<port>", or a bare
             CIDR for port 22, as records from before ssh_ports read), the interface, or for "ad"
             "<proto>@<CIDR>@<ports>" (security/firewall_rules).
    Returns: list of str.
    Fails:   KeyError for another kind.
    Feeds:   setup/configure_firewall (adds, forgets), undo/undo_firewall (removes)."""
    if kind == "dhcp":
        return ["in", "on", what, "to", "any", "port", "67", "proto", "udp"]
    if kind == "ad":
        proto, cidr, ports = what.split("@")
        return ["from", cidr, "to", "any", "port", ports, "proto", proto]
    if kind == "ssh":
        cidr, _, port = what.partition("@")
        return ["from", cidr, "to", "any", "port", port or "22", "proto", "tcp"]
    port, proto = {"ntp": ("123", "udp")}[kind]
    return ["from", what, "to", "any", "port", port, "proto", proto]

