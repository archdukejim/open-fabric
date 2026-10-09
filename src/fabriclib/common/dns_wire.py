import random
import struct


def dns_wire_query(name):
    """Purpose: a DNS A-record query in wire format (RFC 1035), for UDP and DNS-over-HTTPS alike.
    Inputs:  name — host name (a trailing dot is ignored).
    Returns: bytes (a random id, recursion desired, one question, class IN).
    Fails:   never (labels longer than 63 bytes are not checked).
    Feeds:   dns_query, doh_query."""
    labels = b"".join(bytes([len(p)]) + p.encode() for p in name.rstrip(".").split("."))
    return struct.pack(">HHHHHH", random.randint(0, 65535), 0x0100, 1, 0, 0, 0) + labels + b"\0" + \
        struct.pack(">HH", 1, 1)


def dns_wire_answers(query, data):
    """Purpose: the IPv4 answers of a reply to dns_wire_query.
    Inputs:  query — the bytes sent; data — the reply.
    Returns: list of dotted IPv4 strings (CNAMEs skipped, the A records they lead to kept); [] for none.
    Fails:   struct.error or IndexError on a truncated or malformed reply.
    Feeds:   dns_query, doh_query.
    Notes:   no check of the reply's id or rcode; the answers are read right after the question, assuming the server
             echoed it unchanged."""
    answers = struct.unpack(">H", data[6:8])[0]
    i, found = len(query), []
    for _ in range(answers):
        while data[i] and data[i] < 0xC0:        # skip the owner name
            i += data[i] + 1
        i += 2 if data[i] >= 0xC0 else 1
        rtype, _, _, rdlen = struct.unpack(">HHIH", data[i:i + 10])
        i += 10
        if rtype == 1 and rdlen == 4:
            found.append(".".join(map(str, data[i:i + 4])))
        i += rdlen
    return found
