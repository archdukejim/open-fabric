import random
import socket
import struct


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
    Notes:   no TCP fallback and no check of the reply's id or rcode; the answer section is read right after
             the question, assuming the server echoed it unchanged."""
    qid = random.randint(0, 65535)
    labels = b"".join(bytes([len(p)]) + p.encode() for p in name.rstrip(".").split("."))
    query = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + labels + b"\0" + struct.pack(">HH", 1, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(query, (server, port))
        data = s.recv(4096)
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
