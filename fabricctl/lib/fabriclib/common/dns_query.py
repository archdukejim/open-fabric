import random
import socket
import struct


def dns_query(name, server, port=53, timeout=3):
    """A-record lookup straight against one DNS server (stdlib only, so
    checks do not depend on dig). Returns the list of IPv4 answers,
    following CNAMEs within the same response."""
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
