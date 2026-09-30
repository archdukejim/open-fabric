import ipaddress
import re

DNS_RE = re.compile(r"^(\*\.)?(?!-)[A-Za-z0-9_-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9_-]{1,63}(?<!-))*\.?$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}$")


def valid_san(name):
    """'dns' | 'ip' | 'email' for an acceptable subject alternative name,
    None otherwise (URIs, other names and malformed values)."""
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
