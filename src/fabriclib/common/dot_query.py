import socket
import ssl
import struct

from fabriclib.common.dns_wire import dns_wire_answers, dns_wire_query


def _read(sock, n):
    """Purpose: exactly n bytes from a socket.
    Inputs:  sock — a connected socket; n — int.
    Returns: bytes.
    Fails:   ConnectionError when the server closes first; OSError (socket.timeout) from recv.
    Feeds:   dot_query."""
    data = b""
    while len(data) < n:
        chunk = sock.recv(n - len(data))
        if not chunk:
            raise ConnectionError("the server closed the connection")
        data += chunk
    return data


def dot_query(name, host, ip, root_ca, port=853, timeout=10):
    """Purpose: an A-record lookup over DNS-over-TLS (RFC 7858), for doctor's health check (manual 1.12.2.16): to ip,
             the certificate verified against root_ca for host.
    Inputs:  name — host name to look up; host — the name the certificate must carry (hostname_bind9); ip — the
             address to connect to; root_ca — fabric's root CA file; port — default 853; timeout — seconds.
    Returns: list of IPv4 answers ([] for none).
    Fails:   ssl.SSLError (certificate not trusted or not for host), OSError (refused, timed out), ConnectionError,
             struct.error or IndexError on a malformed reply.
    Feeds:   setup/verify_install."""
    query = dns_wire_query(name)
    ctx = ssl.create_default_context(cafile=root_ca)
    with socket.create_connection((ip, port), timeout=timeout) as raw:
        with ctx.wrap_socket(raw, server_hostname=host) as tls:
            tls.sendall(struct.pack(">H", len(query)) + query)
            size = struct.unpack(">H", _read(tls, 2))[0]
            return dns_wire_answers(query, _read(tls, size))
