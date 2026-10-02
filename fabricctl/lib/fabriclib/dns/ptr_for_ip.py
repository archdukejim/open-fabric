import ipaddress

# RFC 1918 and CGNAT (ipaddress's is_private also counts documentation and reserved ranges)
PRIVATE_V4 = [ipaddress.ip_network(n) for n in ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "100.64.0.0/10")]
ULA = ipaddress.ip_network("fc00::/7")


def ptr_for_ip(ip):
    """Purpose: Where an address's automatic PTR record lives, or why it gets none.
    Inputs:  ip — str (or anything whose str() is an address).
    Returns: (reverse zone, label): a /24 in-addr.arpa zone and the last octet for private IPv4 (RFC 1918, CGNAT); a /64
             ip6.arpa zone and 16 nibbles for IPv6 ULA; or (None, reason) for an invalid, loopback, link-local,
             unspecified, multicast, public or global address.
    Fails:   never — a bad address returns (None, "not an IP address").
    Feeds:   reverse_zones, zone_detail; the web UI's dev preview (webui/devpreview).
    Notes:   serving a public address's reverse zone locally would shadow someone else's network.
    """
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        return None, "not an IP address"
    if addr.is_loopback or addr.is_link_local or addr.is_unspecified or addr.is_multicast:
        return None, "loopback, link-local or multicast address"
    if addr.version == 4:
        if not any(addr in net for net in PRIVATE_V4):
            return None, "public address (its reverse zone belongs to its owner)"
        octets = str(addr).split(".")
        return f"{octets[2]}.{octets[1]}.{octets[0]}.in-addr.arpa", octets[3]
    if addr not in ULA:
        return None, "global IPv6 address (its reverse zone belongs to its owner)"
    nibbles = addr.exploded.replace(":", "")[::-1]          # 32 nibbles, least significant first
    return ".".join(nibbles[16:]) + ".ip6.arpa", ".".join(nibbles[:16])
