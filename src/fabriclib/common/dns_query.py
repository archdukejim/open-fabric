import socket

from fabriclib.common.dns_wire import dns_wire_answers, dns_wire_query


def dns_query(name, server, port=53, timeout=3):
    """Purpose: A-record lookup straight against one DNS server over UDP, stdlib only, so checks do not
             depend on dig.
    Inputs:  name — str, the host name (a trailing dot is ignored); server — str, IPv4 address of the server;
             port — int, default 53; timeout — seconds for the reply, default 3.
    Returns: list of IPv4 answers as dotted strings (CNAMEs in the same response are skipped, the A records
             they lead to are kept); empty if the answer has none (including NXDOMAIN).
    Fails:   socket.timeout (OSError) if no reply in time; OSError on a network error; struct.error or
             IndexError on a truncated or malformed reply. Labels longer than 63 bytes are not checked.
    Feeds:   setup/verify_install.py.
    Notes:   no TCP fallback and no check of the reply's id or rcode (dns_wire)."""
    query = dns_wire_query(name)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(query, (server, port))
        data = s.recv(4096)
    return dns_wire_answers(query, data)
