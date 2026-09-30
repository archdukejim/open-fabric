import ipaddress
import re

DNS_RE = re.compile(r"^(\*\.)?(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9_-]{1,63}(?<!-))*\.?$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}$")


def valid_san(name):
    """Purpose: Classify a subject alternative name that fabric's signing policy accepts.
    Inputs:  name — any value (str()-ed and stripped).
    Returns: "ip" (IPv4 or IPv6 address), "email", "dns" (host name, optional leading "*." wildcard and
             trailing dot, at most 253 characters), or None (URIs, other names, malformed values).
    Fails:   never — every value gets an answer.
    Feeds:   describe_csr, issue_key_pair.
    """
    name = str(name).strip()
    try:
        ipaddress.ip_address(name)
        return "ip"
    except ValueError:
        pass
    if EMAIL_RE.match(name):
        return "email"
    if len(name) <= 253 and DNS_RE.match(name):
        return "dns"
    return None
